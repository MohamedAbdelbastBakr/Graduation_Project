# Real-Time AI-Powered Translation System  

## Table of Contents  
- [Overview](#overview)  
- [Objective](#objective)  
- [System Architecture](#system-architecture)
- [Block Diagram](#block-diagram)  
- [Features](#features)  
- [Tech Stack](#tech-stack)  
- [Pipeline Workflow](#pipeline-workflow)  
- [System Components](#system-components)  
- [Video](#video)   
- [Team](#team)  


## Overview  
The **Real-Time AI-Powered Translation System** addresses the universal challenge of language barriers by enabling real-time multilingual communication. The system uses a Raspberry Pi Pico W to capture speech, processes it through advanced AI models on a laptop, and broadcasts the translated speech to all attendees in real time. Additionally, the system features a **Streamlit-based GUI** for user-friendly interaction.  



## Objective  
The primary goal of this project is to eliminate language barriers and facilitate smooth communication in real-time, enhancing inclusivity and understanding across diverse languages.  



## System Architecture  
1. **Input Device**: Raspberry Pi Pico W with integrated Wi-Fi captures speech via a microphone.  
2. **Processing Unit**: A laptop runs the AI-powered pipeline.  
3. **GUI**: Streamlit application for user interaction and control.  
4. **AI Models in the Pipeline**:  
   - **Silero VAD**: Detects and segments speech from silence.  
   - **Whisper**: Converts speech to English text.  
   - **VITS**: Converts the translated text to high-quality speech.  
5. **Multithreaded Design**: Utilizes separate threads and queues for efficient processing of audio and text data.  



## Block Diagram
![WhatsApp Image 2025-01-15 at 16 15 32_275cef88](https://github.com/user-attachments/assets/eab6133c-bfb4-469b-b114-d1ae429fa425)


## Features  
- Real-time speech-to-speech translation.  
- Streamlit-based GUI for controlling the system and displaying results.  
- Multithreaded design with efficient queue-based communication.  
- Language-independent communication.  
- Broadcasts translated speech for seamless interaction.  



## Tech Stack  
- **Hardware**: Raspberry Pi Pico W  
- **Programming Languages**: Python  
- **Framework**: Streamlit (for GUI)  
- **AI Models**:  
  - Silero VAD  
  - Whisper  
  - VITS  
- **Protocol**: UDP  
- **Sample Rate**: 16,000 Hz  



## Pipeline Workflow  
1. **Recording Thread**: Captures audio from the microphone and prepares it for processing by reading audio chunks.  
2. **VAD Thread**:  
   - Analyzes audio chunks for speech presence.  
   - Confidence > 0.4: Speech data is stored.  
   - Confidence ≤ 0.4: Checks for 25 ms silence before passing speech data.  
3. **Speech-to-Text Thread**: Converts detected speech segments to English text using the Whisper model.  
4. **Text-to-Speech Thread**: Converts transcribed text to speech using the VITS model.  
5. **Queue Management**:  
   - **Receiving Queue**: Holds audio chunks until processed by VAD.  
   - **Input Speech Queue**: Receives speech segments for transcription.  
   - **Text Queue**: Manages flow of transcriptions to TTS.  
   - **Output Speech Queue**: Stores generated speech audio for playback.  



## System Components  
- **Streamlit GUI**:  
  - Allows control of audio input sources.  
  - Displays transcriptions and translated speech output.  
  - Enables interaction with system commands via a Command Queue.  
- **Multithreading**:  
  - Efficient processing of data streams through parallel threads.  
  - Real-time performance maintained by queue-based communication.  



## Video  

https://github.com/user-attachments/assets/08dc1f10-639a-4693-b8d5-7be216c9695c

## Team

This is our graduation project from Benha University 2024. I am grateful to my team **[Mohamed ElSayed](https://github.com/MohamedPyTorch)**, **[Mahmoud Mohamed](https://github.com/Ma7moud88838)**, **[Mohamed Gamal](https://github.com/mohamedgamal322)**, and **[Mohamed Yahya](https://github.com/yaya0001)**. Their dedication and collaborative spirit were instrumental in achieving an excellent grade in this graduation project.
