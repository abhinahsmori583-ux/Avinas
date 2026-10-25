import json, os, subprocess, sys
import requests

job_dir = sys.argv[1]
manifest = json.load(open(os.path.join(job_dir, 'manifest.json'), encoding='utf-8'))

def run(cmd):
    subprocess.run(cmd, check=True)

def probe(path, entries, stream=None):
    cmd = ['ffprobe', '-v', 'error']
    if stream:
        cmd += ['-select_streams', stream]
    cmd += ['-show_entries', entries, '-of', 'json', path]
    return json.loads(subprocess.check_output(cmd))

voice = os.path.join(job_dir, 'voice.wav')
voice_len = float(probe(voice, 'format=duration')['format']['duration'])
clips = manifest['clips']
per = (voice_len + 0.5) / len(clips)

parts = []
for i, c in enumerate(clips):
    raw = os.path.join(job_dir, 'raw%d.mp4' % i)
    seg = os.path.join(job_dir, 'seg%d.mp4' % i)
    r = requests.get(c['url'], timeout=120)
    r.raise_for_status()
    open(raw, 'wb').write(r.content)
    run(['ffmpeg', '-y', '-loglevel', 'error', '-stream_loop', '-1', '-i', raw, '-t', '%.2f' % per,
         '-vf', 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1',
         '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', seg])
    parts.append(seg)

list_file = os.path.join(job_dir, 'list.txt')
with open(list_file, 'w') as f:
    for p in parts:
        f.write("file '%s'\n" % os.path.basename(p))
video = os.path.join(job_dir, 'video.mp4')
run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', list_file, '-c', 'copy', video])

lines = [l.strip() for l in manifest['subtitle_lines'] if l.strip()]
total = sum(len(l) for l in lines)
def ts(t):
    ms = int(round(t * 1000))
    return '%02d:%02d:%02d,%03d' % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)
srt = os.path.join(job_dir, 'subs.srt')
t = 0.0
with open(srt, 'w', encoding='utf-8') as f:
    for n, l in enumerate(lines, 1):
        d = voice_len * len(l) / total
        f.write('%d\n%s --> %s\n%s\n\n' % (n, ts(t), ts(t + d), l))
        t += d

final = os.path.join(job_dir, 'final.mp4')
style = 'FontName=Noto Sans Devanagari,FontSize=12,Alignment=2,MarginV=250,Outline=2,PrimaryColour=&H00FFFFFF'
run(['ffmpeg', '-y', '-loglevel', 'error', '-i', video, '-i', voice,
     '-vf', "subtitles=%s:force_style='%s'" % (srt, style),
     '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p',
     '-c:a', 'aac', '-shortest', '-movflags', '+faststart', final])

for p in parts + [list_file, video] + [os.path.join(job_dir, 'raw%d.mp4' % i) for i in range(len(clips))]:
    try:
        os.remove(p)
    except OSError:
        pass

v = probe(final, 'stream=width,height', 'v:0')['streams'][0]
has_audio = len(probe(final, 'stream=codec_type', 'a:0')['streams']) > 0
dur = float(probe(final, 'format=duration')['format']['duration'])
result = {'job_id': manifest['job_id'], 'ok': True, 'width': v['width'], 'height': v['height'],
          'duration': round(dur, 1), 'has_audio': has_audio,
          'has_subtitles': os.path.getsize(srt) > 0,
          'size_bytes': os.path.getsize(final)}
json.dump(result, open(os.path.join(job_dir, 'result.json'), 'w'))
print(result)
