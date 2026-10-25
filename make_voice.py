import json, os, subprocess, sys, wave, urllib.request

job_dir = sys.argv[1]
manifest = json.load(open(os.path.join(job_dir, 'manifest.json'), encoding='utf-8'))
text = manifest.get('script_hi', '').strip()
if len(text) < 50:
    sys.exit('make_voice: script_hi is missing or too short')

base = 'https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/priyamvada/medium/hi_IN-priyamvada-medium'
for ext in ('.onnx', '.onnx.json'):
    urllib.request.urlretrieve(base + ext, 'voice_model' + ext)

out = os.path.join(job_dir, 'voice.wav')
subprocess.run(['python', '-m', 'piper', '-m', 'voice_model.onnx', '--length_scale', '1.15', '-f', out],
               input=text.encode('utf-8'), check=True)

with wave.open(out) as w:
    seconds = w.getnframes() / w.getframerate()
if seconds < 15 or seconds > 70:
    sys.exit('make_voice: voice length %.1fs is outside 15-70s' % seconds)
print('voice ok: %.1fs' % seconds)
