#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include <FFat.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <WebSocketsClient.h>
#include <driver/i2s.h>
#include <mbedtls/base64.h>
#include <functional>
#include "WireGuard.h"
#if __has_include("secrets.h")
#include "secrets.h"
#else
#include "secrets.example.h"
#endif

namespace emobot {
class CloudVoice {
  std::function<void(const String&)> emit;
  TaskHandle_t worker=nullptr;
  bool mounted=false, audioReady=false;
  JsonDocument history;
  static void task(void* self) { static_cast<CloudVoice*>(self)->conversation(); }
  bool ready() {
    return mounted && audioReady && WiFi.status()==WL_CONNECTED && time(nullptr)>1700000000 && strlen(EMOBOT_API_KEY)>0 && strlen(EMOBOT_ROOT_CA)>0;
  }
  String post(const char* url, Stream& body, size_t size) {
    WiFiClientSecure secure; secure.setCACert(EMOBOT_ROOT_CA); secure.setTimeout(12000);
    HTTPClient request; request.setTimeout(20000); request.setConnectTimeout(8000);
    if (!request.begin(secure,url)) return "";
    request.addHeader("Content-Type","application/json");
    request.addHeader("Authorization",String("Bearer ")+EMOBOT_API_KEY);
    int status=request.sendRequest("POST",&body,size);
    String result;
    // Streaming parse is bounded even when a remote server omits Content-Length.
    if (status==200 && request.getSize()<=16384) {
      WiFiClient* stream=request.getStreamPtr();
      uint32_t started=millis();
      while (request.connected() && millis()-started<20000 && result.length()<16384) {
        while (stream->available() && result.length()<16384) result+=char(stream->read());
        if (request.getSize()>=0 && result.length()>=size_t(request.getSize())) break;
        delay(2);
      }
    }
    request.end();
    return result;
  }
  static void little(uint8_t* p, uint32_t value, int count) { for (int i=0;i<count;++i) p[i]=(value>>(8*i))&255; }
  bool record() {
    File recording=FFat.open("/voice.wav",FILE_WRITE);
    if (!recording) return false;
    uint8_t header[44]={};
    memcpy(header,"RIFF",4); memcpy(header+8,"WAVEfmt ",8); memcpy(header+36,"data",4);
    little(header+16,16,4); little(header+20,1,2); little(header+22,1,2);
    little(header+24,16000,4); little(header+28,32000,4); little(header+32,2,2); little(header+34,16,2);
    recording.write(header,44);
    uint32_t captured=0, started=millis(); int32_t samples[256];
    while (captured<320000 && millis()-started<11000) {
      size_t received=0;
      if (i2s_read(I2S_NUM_0,samples,sizeof(samples),&received,pdMS_TO_TICKS(1000))!=ESP_OK || !received) { recording.close(); return false; }
      int16_t mono[256]; size_t count=received/4;
      for (size_t i=0;i<count;++i) mono[i]=constrain(samples[i]>>14,-32768,32767);
      if (recording.write(reinterpret_cast<uint8_t*>(mono),count*2)!=count*2) { recording.close(); return false; }
      captured+=count*2;
    }
    little(header+4,36+captured,4); little(header+40,captured,4);
    recording.seek(0); recording.write(header,44); recording.close(); return captured>0;
  }
  String transcribe() {
    if (!record()) return "";
    File input=FFat.open("/voice.wav",FILE_READ), body=FFat.open("/asr.json",FILE_WRITE);
    if (!input || !body) return "";
    body.print(String("{\"model\":\"")+EMOBOT_ASR_MODEL+"\",\"input\":{\"messages\":[{\"role\":\"user\",\"content\":[{\"audio\":\"data:audio/wav;base64,");
    uint8_t bytes[768], encoded[1025]; size_t written=0;
    while (input.available()) {
      size_t count=input.read(bytes,sizeof(bytes));
      if (mbedtls_base64_encode(encoded,sizeof(encoded),&written,bytes,count)!=0 || body.write(encoded,written)!=written) return "";
    }
    body.print("\"}]}]},\"parameters\":{\"asr_options\":{\"enable_itn\":true}}}");
    input.close(); body.close();
    body=FFat.open("/asr.json",FILE_READ);
    String response=post(EMOBOT_ASR_URL,body,body.size()); body.close();
    JsonDocument document;
    if (deserializeJson(document,response)) return "";
    return document["output"]["choices"][0]["message"]["content"][0]["text"].as<String>();
  }
  String respond(const String& question) {
    JsonDocument request;
    request["model"]=EMOBOT_CHAT_MODEL; request["temperature"]=0.5; request["max_tokens"]=1200;
    JsonArray messages=request["messages"].to<JsonArray>();
    JsonObject system=messages.add<JsonObject>(); system["role"]="system";
    String instruction=String("You are Emobot, a warm desk robot. Reply in ")+language+". Be honest and supportive. No diagnosis or invented memories. Return JSON only: {\"reply\":\"brief response\",\"actions\":[{\"action\":\"eye_happy\",\"duration\":700}]}. At most 12 actions, 50-5000ms each, total <=20000ms. Persona: "+persona+". Allowed: delay";
    for (auto name : eyes) instruction+=String(",")+name;
    for (auto name : heads) instruction+=String(",")+name;
    for (auto name : clips) instruction+=String(",")+name;
    system["content"]=instruction;
    for (JsonVariant message : history.as<JsonArray>()) messages.add(message);
    JsonObject user=messages.add<JsonObject>(); user["role"]="user"; user["content"]=question;
    File body=FFat.open("/chat.json",FILE_WRITE); if (!body) return "";
    serializeJson(request,body); body.close(); body=FFat.open("/chat.json",FILE_READ);
    String response=post(EMOBOT_CHAT_URL,body,body.size()); body.close();
    JsonDocument envelope, answer;
    if (deserializeJson(envelope,response)) return "";
    String content=envelope["choices"][0]["message"]["content"].as<String>();
    if (deserializeJson(answer,content) || !answer["reply"].is<const char*>() || !answer["actions"].is<JsonArray>()) return "";
    String reply=answer["reply"].as<String>();
    if (!reply.length() || reply.length()>4000) return "";
    uint32_t total=0;
    if (answer["actions"].size()>12) return "";
    for (JsonVariant action : answer["actions"].as<JsonArray>()) {
      if (!action["action"].is<const char*>() || !action["duration"].is<int>() || !validAction(action["action"].as<String>())) return "";
      int duration=action["duration"].as<int>(); if (duration<50 || duration>5000) return "";
      total+=duration;
    }
    if (total>20000) return "";
    JsonDocument movement; movement["actions"]=answer["actions"]; String frame; serializeJson(movement,frame); emit(frame);
    JsonArray turns=history.as<JsonArray>();
    JsonObject q=turns.add<JsonObject>(); q["role"]="user"; q["content"]=question;
    JsonObject a=turns.add<JsonObject>(); a["role"]="assistant"; a["content"]=reply;
    while (turns.size()>20) turns.remove(0);
    File saved=FFat.open("/history.json",FILE_WRITE); if (saved) { serializeJson(history,saved); saved.close(); }
    return reply;
  }
  bool speak(const String& reply) {
    if (!strlen(EMOBOT_TTS_TOKEN) || !strlen(EMOBOT_TTS_APP)) return false;
    WebSocketsClient connection; bool done=false, failed=false, sent=false;
    String authorization=String("Authorization: Bearer; ")+EMOBOT_TTS_TOKEN;
    connection.setExtraHeaders(authorization.c_str());
    connection.onEvent([&](WStype_t event,uint8_t* data,size_t length) {
      if (event==WStype_CONNECTED) {
        JsonDocument request;
        request["app"]["appid"]=EMOBOT_TTS_APP; request["app"]["token"]=EMOBOT_TTS_TOKEN; request["app"]["cluster"]=EMOBOT_TTS_CLUSTER;
        request["user"]["uid"]=WiFi.macAddress();
        request["audio"]["voice_type"]=EMOBOT_TTS_VOICE; request["audio"]["encoding"]="pcm"; request["audio"]["rate"]=16000;
        request["request"]["reqid"]=String(esp_random(),HEX)+String(esp_random(),HEX);
        request["request"]["text"]=reply; request["request"]["operation"]="submit"; request["request"]["text_type"]="plain";
        String json; serializeJson(request,json);
        size_t size=json.length(); uint8_t* packet=new(std::nothrow) uint8_t[size+8];
        if (!packet) { failed=true; return; }
        packet[0]=0x11; packet[1]=0x10; packet[2]=0x10; packet[3]=0;
        for (int i=0;i<4;++i) packet[4+i]=(size>>(24-8*i))&255;
        memcpy(packet+8,json.c_str(),size); sent=connection.sendBIN(packet,size+8); delete[] packet;
        if (!sent) failed=true;
      } else if (event==WStype_BIN) {
        AudioPacket packet;
        if (!parseAudio(data,length,packet)) { failed=true; return; }
        size_t cursor=0;
        while (cursor<packet.bytes) {
          int16_t samples[256]; size_t count=min(size_t(256),(packet.bytes-cursor)/2);
          for (size_t i=0;i<count;++i) { int16_t raw=int16_t(uint16_t(packet.pcm[cursor+i*2]) | uint16_t(packet.pcm[cursor+i*2+1])<<8); samples[i]=raw/3; }
          size_t written=0;
          if (i2s_write(I2S_NUM_1,samples,count*2,&written,pdMS_TO_TICKS(2000))!=ESP_OK || written!=count*2) { failed=true; return; }
          cursor+=count*2;
        }
        done=packet.last;
      } else if (event==WStype_ERROR || (event==WStype_DISCONNECTED && sent && !done)) failed=true;
    });
    connection.beginSslWithCA("openspeech.bytedance.com",443,"/api/v1/tts/ws_binary",EMOBOT_ROOT_CA,"");
    uint32_t started=millis();
    while (!done && !failed && millis()-started<90000) { connection.loop(); delay(5); }
    connection.disconnect(); i2s_zero_dma_buffer(I2S_NUM_1); return done && !failed;
  }
  void conversation() {
    phase=1;
    String question=transcribe();
    phase=2;
    String reply=question.length()?respond(question):"";
    phase=3;
    bool spoken=reply.length() && speak(reply);
    JsonDocument result; result["voice"]=spoken?"ok":"failed";
    String message; serializeJson(result,message); emit(message);
    for (const char* file : {"/voice.wav","/asr.json","/chat.json"}) FFat.remove(file);
    phase=0; worker=nullptr;
    vTaskDelete(nullptr);
  }
public:
  volatile uint8_t phase=0;
  String language="zh", persona="Be warm, concise, curious and respectful.";
  void begin(std::function<void(const String&)> callback) {
    emit=callback; mounted=FFat.begin(false);
    if (mounted) {
      File saved=FFat.open("/history.json",FILE_READ);
      if (!saved || deserializeJson(history,saved) || !history.is<JsonArray>()) history.to<JsonArray>();
      saved.close();
      while (history.size()>20) history.as<JsonArray>().remove(0);
    }
    pinMode(3,OUTPUT); digitalWrite(3,HIGH); pinMode(20,INPUT);
    i2s_config_t input={}; input.mode=i2s_mode_t(I2S_MODE_MASTER|I2S_MODE_RX); input.sample_rate=16000;
    input.bits_per_sample=I2S_BITS_PER_SAMPLE_32BIT; input.channel_format=I2S_CHANNEL_FMT_ONLY_LEFT;
    input.communication_format=I2S_COMM_FORMAT_STAND_I2S; input.dma_buf_count=4; input.dma_buf_len=256;
    i2s_pin_config_t inPins={}; inPins.bck_io_num=21; inPins.ws_io_num=46; inPins.data_out_num=-1; inPins.data_in_num=14;
    i2s_config_t output=input; output.mode=i2s_mode_t(I2S_MODE_MASTER|I2S_MODE_TX); output.bits_per_sample=I2S_BITS_PER_SAMPLE_16BIT;
    i2s_pin_config_t outPins={}; outPins.bck_io_num=17; outPins.ws_io_num=18; outPins.data_out_num=19; outPins.data_in_num=-1;
    audioReady=i2s_driver_install(I2S_NUM_0,&input,0,nullptr)==ESP_OK && i2s_set_pin(I2S_NUM_0,&inPins)==ESP_OK && i2s_driver_install(I2S_NUM_1,&output,0,nullptr)==ESP_OK && i2s_set_pin(I2S_NUM_1,&outPins)==ESP_OK;
  }
  bool trigger() {
    if (worker || !ready()) return false;
    return xTaskCreatePinnedToCore(task,"emobot-voice",12288,this,1,&worker,0)==pdPASS;
  }
};
}
