import streamlit as st
import webrtcvad
# Accepts 16-bit mono PCM audio sampled at 8000, 16000, or 32000 Hz.
# Frames must be 10, 20, or 30 ms in duration.

import check_rasp_connection as rp
import multiprocessing as mp
from scipy.io import wavfile
import torch
import pyaudio
import sounddevice as sd
import numpy as np
import noisereduce as nr
from queue import Queue
import threading
import socket
from transformers import WhisperProcessor, WhisperForConditionalGeneration, VitsTokenizer, VitsModel, set_seed

#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>    Recording     <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
def Record_thread(Receiving_Q, comm_q):
    receiving_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiving_socket.bind(("0.0.0.0", 12345))
    p = pyaudio.PyAudio()
    IN_st = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=16000,
                    input=True,
                    frames_per_buffer=2048) 
    OUT_st = sd.OutputStream(channels=1, dtype="int16", samplerate=16000)
    OUT_st.start()
    last_state = "stop"
    while True:
        if not comm_q.empty():
            last_state = comm_q.get()
            OUT_st.stop()
            OUT_st.close()
            if (last_state == "dev_org"):
                OUT_st = sd.OutputStream(channels=1, dtype=np.int16, samplerate=16000)
                OUT_st.start()
            elif (last_state == "rem_org"):
                OUT_st = sd.OutputStream(channels=1, dtype=np.int8, samplerate=16000)
                OUT_st.start()
        if (last_state == "dev_org") or (last_state == "dev"):
            chunk = IN_st.read(2048)
            audio_chunk = np.frombuffer(chunk, dtype=np.int16)
            Receiving_Q.put(audio_chunk)
            if last_state == "dev_org":
                OUT_st.write(audio_chunk)
        elif (last_state == "rem_org") or (last_state == "rem"):
            chunk, server_addr = receiving_socket.recvfrom(2048)
            audio_chunk = np.frombuffer(chunk, dtype=np.uint8)
            audio_chunk = np.array((audio_chunk - 128) , dtype=np.int8)
            Receiving_Q.put(audio_chunk)
            if last_state == "rem_org":
                OUT_st.write(audio_chunk)

#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>    Applying VAD     <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
def VAD_thread(Receiving_Q, IN_Speech_Q, Denum_Q):
    model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                                  model='silero_vad',
                                  force_reload=False)
    Speech_Chunk = np.array([], dtype = np.float32)
    Silence_Chunk = np.array([], dtype = np.float32)
    denum = 32767
    while True:
        if not Denum_Q.empty():
            denum = int(Denum_Q.get())
            Speech_Chunk = np.array([], dtype = np.float32)
            Silence_Chunk = np.array([], dtype = np.float32)
            
        if not Receiving_Q.empty():
            audio = Receiving_Q.get()
            audio = np.array(audio / denum, dtype=np.float32)
            for _ in range(4):
                frame = audio[0:512]
                audio = audio[512:]
                new_confidence = model(torch.from_numpy(frame), 16000).item()
                if (new_confidence > 0.4):
                    Speech_Chunk = np.concatenate((Speech_Chunk, Silence_Chunk, frame))
                    Silence_Chunk = np.array([], dtype = np.float32)
                    
                else:
                    Silence_Chunk = np.concatenate((Silence_Chunk, frame))
                    if(len(Silence_Chunk) > 8000):
                        if(len(Speech_Chunk) > 12800):
                            Speech_Chunk = np.concatenate((Speech_Chunk, Silence_Chunk))
                            IN_Speech_Q.put(Speech_Chunk)
                            print("detect_sentence-------------------------------")
                        Speech_Chunk = np.array([], dtype = np.float32)
                        Silence_Chunk = np.array([], dtype = np.float32)
            

#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>    Translate Speech    <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
def speech_to_text(IN_Speech_Q, Text_Q, OUT_Text_Q):
    Processor = WhisperProcessor.from_pretrained("openai/whisper-medium")
    Whisper_model = WhisperForConditionalGeneration.from_pretrained("openai/whisper-medium").to('cuda')
    Forced_decoder_ids = Processor.get_decoder_prompt_ids(language="arabic", task="translate")
    while True:
        if not IN_Speech_Q.empty():
            input_speech = np.array(IN_Speech_Q.get(), dtype = np.float32)
            
            input_features = Processor(input_speech, sampling_rate=16000, return_tensors="pt").input_features.to('cuda')
            
            # generate token ids
            predicted_ids = Whisper_model.generate(input_features, forced_decoder_ids=Forced_decoder_ids)
            
            # decode token ids to text
            transcription = Processor.batch_decode(predicted_ids, skip_special_tokens=True)
            
            Text_Q.put(transcription)
            OUT_Text_Q.put(transcription[0])
            print(transcription)

#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>    Convert text to speech again    <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
def text_to_speech(Text_Q, OUT_Speech_Q, Loading_Q):
    tokenizer = VitsTokenizer.from_pretrained("facebook/mms-tts-eng")
    VITS_model = VitsModel.from_pretrained("facebook/mms-tts-eng").to("cuda")
    loaded = True
    while True:
        if not Text_Q.empty():
            inputs = tokenizer(text=Text_Q.get(), return_tensors="pt")
            set_seed(555)  # make deterministic
            with torch.no_grad():
                outputs = VITS_model(**inputs.to("cuda"))
        
            waveform = outputs.waveform[0]
            waveform = waveform.cpu().float().numpy()
            OUT_Speech_Q.put(waveform)
            if loaded:
                Loading_Q.put("loaded")
                loaded = False
    
#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>    Starting Threads    <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
if __name__ == "__main__":
        
    if 'loading_state' not in st.session_state:
        st.session_state.loading_state = False
    
    if 'Loading_Q' not in st.session_state:
        st.session_state.Loading_Q = mp.Queue()
    
    if 'Denum_Q' not in st.session_state:
        st.session_state.Denum_Q = mp.Queue()
    
    if 'Receiving_Q' not in st.session_state:
        st.session_state.Receiving_Q = mp.Queue()
    
    if 'IN_Speech_Q' not in st.session_state:
        st.session_state.IN_Speech_Q = mp.Queue()
        _, d = wavfile.read(r"ready.wav")
        d = np.array(d / 32767, dtype = np.float32)
        st.session_state.IN_Speech_Q.put(d)
        
    if 'Text_Q' not in st.session_state:
        st.session_state.Text_Q = mp.Queue()
        
    if 'Comm_Q' not in st.session_state:
        st.session_state.Comm_Q = mp.Queue()
        
    if 'OUT_Speech_Q' not in st.session_state:
        st.session_state.OUT_Speech_Q = mp.Queue()
        
    if 'OUT_Text_Q' not in st.session_state:
        st.session_state.OUT_Text_Q = mp.Queue()

    if 'p1' not in st.session_state:
        st.session_state.p1 = mp.Process(target=Record_thread, args=(st.session_state.Receiving_Q, st.session_state.Comm_Q))
        st.session_state.p1.start()
    
    if 'p2' not in st.session_state:
        st.session_state.p2 = mp.Process(target=VAD_thread, args=(st.session_state.Receiving_Q, st.session_state.IN_Speech_Q, st.session_state.Denum_Q))
        st.session_state.p2.start()
    
    if 'p3' not in st.session_state:
       st.session_state.p3 = mp.Process(target=speech_to_text, args=(st.session_state.IN_Speech_Q, st.session_state.Text_Q, st.session_state.OUT_Text_Q))
       st.session_state.p3.start()
    
    if 'p4' not in st.session_state:
       st.session_state.p4 = mp.Process(target=text_to_speech, args=(st.session_state.Text_Q, st.session_state.OUT_Speech_Q,  st.session_state.Loading_Q))
       st.session_state.p4.start()
    
#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>    Streamlit GUI   <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    if not st.session_state.loading_state:  
        with st.spinner("Wait while loading models..."):
            while True:
                if st.session_state.Loading_Q.get() == "loaded":
                    st.session_state.loading_state = True
                    break
    
    with st.sidebar:
        st.markdown("""<font color="black" face="Arial Narrow" size="5"><b>⚙️ Adjust Preferences</b></font>""", unsafe_allow_html=True)
        st.markdown('---')
        Main_Form = st.form("main_form", border=False)
        Microphon = Main_Form.selectbox("**🎤 Choose Recording Mic:**", ("Device mic", "Remote mic 1", "Remote mic 2"))
        Main_Form.markdown('---')
        Output_Speech = Main_Form.radio("**🎧 Listening To:**", ("Translated Speech", "Original Speech"))
        Main_Form.markdown('---')
        Showing_Transcript = Main_Form.checkbox("**💬 Show Transcript !**", value=False)
        Start_butt = Main_Form.form_submit_button("Apply / Start", use_container_width=True)
        Stop_butt = st.button("Stop", use_container_width=True)
            
    
    st.markdown("""<center><font color="black" face="Hacen Casablanca" size="7"><b>Real-Time AI-Powered Translation System
</b></font></center>""", unsafe_allow_html=True)
    st.markdown("""<center><font color="black" face="Aktiv Grotesk" size="5"><b>🎙️ Speech Real-Time Translation</b></font></center>""", unsafe_allow_html=True)
    with st.expander("**About this APP**", expanded=True):
        st.markdown("""<p><font face="Arial Narrow"><b>Our innovative app, developed by [<i><u>BEAUTIFUL MINDS Team</u></i>], helps to break down linguistic barriers effortlessly. this app harnesses state-of-the-art AI and machine learning algorithms to provide seamless real-time speech translation.</b></font></p>""", unsafe_allow_html=True)
        
    Messages_Container = st.container()
    
    OUT_Text = st.empty()
    
    if Start_butt:
        if Microphon == "Device mic":
            st.session_state.Denum_Q.put("32767")
            Messages_Container.write("🗣️:  :green[Start talking now...]")
            if (Output_Speech ==  "Original Speech"):
                st.session_state.Comm_Q.put("dev_org")
            else:
                st.session_state.Comm_Q.put("dev")
        elif (Microphon == "Remote mic 1") or (Microphon == "Remote mic 2"):
            conn = False
            with Messages_Container:
                with st.spinner("Checking Connection..."):
                    if Microphon == "Remote mic 1":
                        conn = rp.check(MAC='28-cd-c1-0f-6a-2c')
                    else:
                        conn = rp.check()
            if conn:
                st.session_state.Denum_Q.put("127")
                Messages_Container.success("😃: Device is connected successfully")
                Messages_Container.write("🗣️:  :green[Start talking now...]")
                if (Output_Speech ==  "Original Speech"):
                    st.session_state.Comm_Q.put("rem_org")
                else:
                    st.session_state.Comm_Q.put("rem")
            else:
                Messages_Container.error("🙁: Device is not connected. check connections and try again.")
                st.session_state.Comm_Q.put("stop")
        
        
    if Stop_butt:
        st.session_state.Comm_Q.put("stop")
        
    while True:
        while st.session_state.OUT_Speech_Q.empty():
            pass
        out_speech = st.session_state.OUT_Speech_Q.get()
        out_text = st.session_state.OUT_Text_Q.get()
        if Showing_Transcript:
            OUT_Text.markdown(out_text)
        if Output_Speech == "Translated Speech":
            sd.play(out_speech, 16000)
            sd.wait()









