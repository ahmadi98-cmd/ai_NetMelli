#!/usr/bin/env python3
"""
AI Melli — Prompt Enhancer + Image Generator
"""

import urllib.request
import urllib.parse
import json
import sys
import os
import time
import random


def enhance_prompt(prompt, negative="", model="openai"):
    """Use AI to enhance the image prompt."""
    sys_prompt = (
        "You are a master AI image prompt engineer. The user gives you a prompt "
        "(may be in any language). Your job: 1) Translate to English if needed. "
        "2) Add detailed style, lighting, composition, mood, quality descriptors. "
        "3) Return ONLY the improved English prompt. No explanations, no quotes, no markdown."
    )

    user_msg = f"User prompt: {prompt}"
    if negative:
        user_msg += f". Also avoid: {negative}"

    payload = json.dumps({
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_msg}
        ],
        "model": model,
        "temperature": 0.7
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://text.pollinations.ai/",
        data=payload,
        method="POST"
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "AI-Melli/1.0")

    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            text = parsed.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not text:
                text = parsed.get("content", "")
            if not text:
                text = str(parsed)
        else:
            text = str(parsed)
    except (json.JSONDecodeError, IndexError, KeyError):
        text = raw

    # Clean up
    text = text.strip().strip('"').strip("'")[:1000]
    return text


def generate_image(prompt, output_path, model="flux", width=1024, height=1024,
                   seed=None, nologo=True, negative=None, retries=2):
    encoded = urllib.parse.quote(prompt, safe='')

    params = {
        "width": width,
        "height": height,
        "model": model,
        "nologo": str(nologo).lower(),
        "nofeed": "true",
    }
    if seed is not None:
        params["seed"] = seed
    if negative:
        params["negative"] = urllib.parse.quote(negative, safe='')

    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"https://image.pollinations.ai/prompt/{encoded}?{query}"

    print(f"  URL: {url[:150]}...")

    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "AI-Melli/1.0")

            with urllib.request.urlopen(req, timeout=180) as resp:
                data = resp.read()

            if len(data) < 500:
                print(f"  Response too small ({len(data)} bytes), retrying...")
                continue

            with open(output_path, "wb") as f:
                f.write(data)

            size_kb = len(data) / 1024
            print(f"  Saved: {output_path} ({size_kb:.1f} KB)")
            return True

        except Exception as e:
            print(f"  Attempt {attempt + 1} failed: {e}")
            if attempt < retries:
                time.sleep(5)

    return False


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ai_melli_config.json"

    with open(config_path, "r") as f:
        config = json.load(f)

    original_prompt = config["prompt"]
    negative = config.get("negative_prompt", "")
    model = config.get("model", "flux")
    enhance_model = config.get("enhance_model", "openai")
    width = int(config.get("width", "1024"))
    height = int(config.get("height", "1024"))
    num = min(int(config.get("num_images", "1")), 10)
    seed = config.get("seed", "")
    nologo = config.get("nologo", "true").lower() == "true"
    out_dir = config.get("output_dir", "output")

    os.makedirs(out_dir, exist_ok=True)

    # Step 1: Enhance prompt
    print("\n=== Step 1: Enhancing Prompt ===")
    print(f"Original: {original_prompt}")

    try:
        enhanced = enhance_prompt(original_prompt, negative, enhance_model)
        print(f"Enhanced: {enhanced}")
        final_prompt = enhanced
        was_enhanced = True
    except Exception as e:
        print(f"Enhancement failed: {e}")
        print("Using original prompt.")
        final_prompt = original_prompt
        was_enhanced = False

    # Step 2: Generate images
    print("\n=== Step 2: Generating Images ===")

    base_seed = None
    if seed and seed.strip():
        try:
            base_seed = int(seed)
        except ValueError:
            base_seed = random.randint(1, 999999)

    ok = 0
    fail = 0
    generated_files = []

    for i in range(1, num + 1):
        print(f"\n--- Image {i}/{num} ---")

        current_seed = base_seed + i - 1 if base_seed is not None else random.randint(1, 999999)

        safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in final_prompt[:50])
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_name}_{timestamp}_{i}.png"
        output_path = os.path.join(out_dir, filename)

        success = generate_image(
            prompt=final_prompt,
            output_path=output_path,
            model=model,
            width=width,
            height=height,
            seed=current_seed,
            nologo=nologo,
            negative=negative if negative else None,
        )

        if success:
            ok += 1
            generated_files.append(filename)
        else:
            fail += 1
            if os.path.exists(output_path):
                os.remove(output_path)

        if i < num:
            time.sleep(3)

    # Save result
    result = {
        "success": ok,
        "failed": fail,
        "enhanced": was_enhanced,
        "original_prompt": original_prompt,
        "final_prompt": final_prompt,
        "files": generated_files,
    }
    with open("/tmp/ai_melli_result.json", "w") as f:
        json.dump(result, f)

    print(f"\n=== Done: {ok} success, {fail} failed ===")

    if ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
