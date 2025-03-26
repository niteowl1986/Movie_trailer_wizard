import os
import subprocess
import whisper
from transformers import pipeline
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip
from scenedetect import detect, ContentDetector

# Step 1: Extract audio from video using FFmpeg
def extract_audio(video_path, audio_path):
    """Extract audio from a video file using FFmpeg."""
    if os.path.exists(audio_path):
        os.remove(audio_path)
    command = ['ffmpeg', '-i', video_path, '-q:a', '0', '-map', 'a', audio_path]
    subprocess.run(command, check=True)
    print(f"Audio extracted to {audio_path}")

# Step 2: Split audio into smaller chunks
def split_audio(audio_path, chunk_duration=600):  # 10 minutes in seconds
    """Split audio into chunks to manage memory."""
    audio = AudioFileClip(audio_path)
    duration = audio.duration
    chunks = []
    for start in range(0, int(duration), chunk_duration):
        end = min(start + chunk_duration, duration)
        chunk_path = f"chunk_{start}_{end}.mp3"
        audio.subclip(start, end).write_audiofile(chunk_path)
        chunks.append((chunk_path, start))
    audio.close()
    return chunks

# Step 3: Transcribe audio chunks using Whisper locally
def transcribe_audio_chunks(chunks):
    """Transcribe each audio chunk using the Whisper base model."""
    model = whisper.load_model("base")  # Lightweight model
    all_segments = []
    for chunk_path, offset in chunks:
        result = model.transcribe(chunk_path, verbose=False)
        segments = result['segments']
        for segment in segments:
            segment['start'] += offset
            segment['end'] += offset
        all_segments.extend(segments)
        os.remove(chunk_path)  # Clean up chunk
    return all_segments

# Step 4: Detect scenes in the video using PySceneDetect
# def detect_scenes(video_path):
#     """Detect distinct scenes in the video."""
#     video_manager = VideoManager([video_path])
#     scene_manager = SceneManager()
#     scene_manager.add_detector(ContentDetector())
#     video_manager.set_downscale_factor()
#     video_manager.start()
#     detect(video_manager, scene_manager)
#     scene_list = scene_manager.get_scene_list()
#     scenes = [(float(scene[0].get_seconds()), float(scene[1].get_seconds())) for scene in scene_list]
#     video_manager.release()
#     return scenes

def detect_scenes(video_path):
    scene_list = detect(video_path, ContentDetector())
    scenes = [(float(scene[0].get_seconds()), float(scene[1].get_seconds())) for scene in scene_list]
    return scenes


# Step 5: Score transcript segments using DistilBERT locally
def score_transcript_segments(segments):
    """Perform sentiment analysis on transcript segments."""
    sentiment_analyzer = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")
    scores = []
    for segment in segments:
        text = segment['text']
        sentiment = sentiment_analyzer(text)[0]
        score = sentiment['score'] if sentiment['label'] == 'POSITIVE' else -sentiment['score']
        scores.append(score)
    return scores

# Step 6: Score scenes based on overlapping transcript segments
def score_scenes(scenes, transcript_segments, segment_scores):
    """Assign scores to scenes based on transcript sentiment."""
    scene_scores = []
    for scene_start, scene_end in scenes:
        overlapping_scores = []
        for segment, score in zip(transcript_segments, segment_scores):
            seg_start = segment['start']
            seg_end = segment['end']
            if seg_start < scene_end and seg_end > scene_start:
                overlapping_scores.append(score)
        scene_score = sum(overlapping_scores) / len(overlapping_scores) if overlapping_scores else 0
        scene_scores.append(scene_score)
    return scene_scores

# Step 7: Select top scenes for the trailer
def select_top_scenes(scenes, scores, total_duration):
    """Select highest-scoring scenes up to target duration, in chronological order."""
    scene_score_pairs = list(zip(scenes, scores))
    scene_score_pairs.sort(key=lambda x: x[1], reverse=True)
    selected = []
    current_duration = 0
    for scene, score in scene_score_pairs:
        scene_duration = scene[1] - scene[0]
        if current_duration + scene_duration <= total_duration:
            selected.append(scene)
            current_duration += scene_duration
    selected.sort(key=lambda x: x[0])  # Sort by start time
    print(f"Selected {len(selected)} scenes with total duration {current_duration} seconds")
    return selected

# Step 8: Generate the trailer using MoviePy
def generate_trailer(video_path, selected_scenes, output_path):
    """Concatenate selected scenes into a trailer."""
    clip = VideoFileClip(video_path)
    trailer_clips = [clip.subclip(start, end) for start, end in selected_scenes]
    trailer = concatenate_videoclips(trailer_clips)
    trailer.write_videofile(output_path, codec="libx264", audio_codec="aac")
    clip.close()
    print(f"Trailer generated at {output_path}")

# Main function to orchestrate the process
def main(video_path,length, output_trailer_path):
    """Process video to generate a trailer."""
    audio_path = "temp_audio.mp3"
    
    print("Extracting audio...")
    extract_audio(video_path, audio_path)
    
    print("Splitting audio into chunks...")
    chunks = split_audio(audio_path)
    
    print("Transcribing audio chunks...")
    transcript_segments = transcribe_audio_chunks(chunks)
    
    print("Detecting scenes...")
    scenes = detect_scenes(video_path)
    
    print("Scoring transcript segments...")
    segment_scores = score_transcript_segments(transcript_segments)
    
    print("Scoring scenes...")
    scene_scores = score_scenes(scenes, transcript_segments, segment_scores)
    
    print("Selecting top scenes...")
    selected_scenes = select_top_scenes(scenes, scene_scores,length)
    
    print("Generating trailer...")
    generate_trailer(video_path, selected_scenes, output_trailer_path)
    
    # Clean up temporary audio file
    if os.path.exists(audio_path):
        os.remove(audio_path)

if __name__ == "__main__":
    video_path = "/Users/ritabrata.das/Movie transcription/The.Adventures.of.Tintin.2011.1080p.BluRay.x264.YIFY.mp4"  # Replace with your video file path
    if not os.path.exists(video_path):
        print(f"Error: Video file {video_path} not found.")
    else:
        dur = input("Enter the duration of the trailer in seconds: ")
        trailer_dir = input("Enter the directory to save the trailer: ") + '.mp4'
        main(video_path,dur,trailer_dir)