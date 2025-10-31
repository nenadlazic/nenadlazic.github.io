---
title: "OpenAI Whisper: Quick audio-to-text and subtitle workflow"
date: 2025-09-25
tags: ["whisper", "transcription", "speech-to-text", "audio"]
categories: ["AI", "Tools", "How-to"]
description: "A concise guide on using OpenAI Whisper to transcribe audio files into text or subtitles quickly and easily."
draft: false
---

Transcribing audio has become essential for creators, developers, and content teams. Whether it's podcasts, YouTube videos, or meeting recordings, having accurate text saves time and makes content more accessible.  

**OpenAI Whisper** is a versatile **speech-to-text tool and library** that leverages pre-trained models to convert audio into text or subtitles. It supports multiple languages, understands context, and can generate time-coded subtitle files.  

Whisper is more than just a command-line tool: it integrates with **FFmpeg**, allowing you to process a wide range of audio and video formats directly. You can use it as a CLI for quick transcriptions, or as a Python library for embedding transcription into custom workflows and applications.  

In this guide, we’ll demonstrate how to take an audio file (or a video with audio), transcribe it with Whisper, and generate **subtitle files** ready for video editors or media players.

## 🛠️ Setup: Installing Whisper

Before running Whisper, you need to ensure that your system has the following tools installed:

- **FFmpeg** – for handling audio and video files  
- **CMake** – required to build Whisper from source  
- **GCC / G++** – for compiling the Whisper binaries  

### Clone the official Whisper repository:
```
git clone https://github.com/ggml-org/whisper.cpp
cd whisper.cpp
```

### Download one of the pretrained model using the provided bash script:
```
sh ./models/download-ggml-model.sh base.en
```

Whisper offers multiple model sizes and language variants. Here’s a quick overview:

- Model sizes:
    - tiny – fastest, lowest accuracy
    - base – fast, moderate accuracy
    - small – balanced speed and accuracy
    - medium – higher accuracy, slower
    - large – highest accuracy, slowest

- Language variants:
    - en – optimized for English transcription
    - multilingual (sometimes written as multilang) – supports multiple languages, useful if your audio contains non-English speech

### Build Whisper using CMake:
```
cmake -B build
cmake --build build --config Release
sudo make install -C build
```

### Prepare audio file for input
```
ffmpeg -i input.ts -vn -ar 16000 -ac 1 -c:a pcm_s16le input_audio.wav
```

### Run Whisper
```
./build/bin/whisper-cli -m ./models/ggml-base.en.bin -f samples/input_audio.wav -ovtt
```

When you run Whisper with the -ovtt flag, the tool generates a WebVTT subtitle file alongside your audio. This file contains:
- Timestamps for each spoken segment
- Transcribed text for each segment
- Proper formatting compatible with video players or editing software

```
WEBVTT

00:00:00.000 --> 00:00:02.500
Hello everyone, welcome to this tutorial.

00:00:02.500 --> 00:00:05.000
Today we are learning how to use OpenAI Whisper.
```

*You can also use the -osrt flag to generate SRT subtitles if your workflow requires that format.*

## Conclusion

OpenAI Whisper makes audio-to-text transcription fast and simple. With the right model and FFmpeg integration, you can generate accurate transcriptions and subtitles in minutes, whether for videos, podcasts, or meetings. It's a versatile tool for both quick CLI usage and integration into custom workflows.
