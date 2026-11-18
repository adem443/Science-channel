import os, sys
from google import genai
from google.genai import types
c = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
names = []
for m in c.models.list():
    n = m.name.replace("models/", "")
    if "image" in n or "imagen" in n:
        names.append(n)
print("IMAGE MODELS:", names, flush=True)
prompt = ("YouTube thumbnail, cartoon illustration, dark night city, a cartoon man in a light-blue sweater "
          "looking shocked next to a glowing light bulb, bold motion lines, high contrast, no text")
ok = False
for n in names:
    try:
        if "imagen" in n:
            r = c.models.generate_images(model=n, prompt=prompt, config=types.GenerateImagesConfig(number_of_images=1))
            data = r.generated_images[0].image.image_bytes
        else:
            r = c.models.generate_content(model=n, contents=prompt)
            data = None
            for p in r.candidates[0].content.parts:
                if getattr(p, "inline_data", None):
                    data = p.inline_data.data
        if data:
            open(f"out_{n}.png", "wb").write(data)
            print("OK ->", n, len(data), flush=True)
            ok = True
        else:
            print("NO IMAGE ->", n, flush=True)
    except Exception as e:
        print("FAIL ->", n, str(e)[:160].replace("\n", " "), flush=True)
print("RESULT:", "WORKS" if ok else "NO FREE IMAGE MODEL", flush=True)
