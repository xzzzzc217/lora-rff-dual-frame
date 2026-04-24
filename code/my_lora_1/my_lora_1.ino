#include <SPI.h>
#include <LoRa.h>

int counter = 0;

void setup() {
  Serial.begin(9600);
  while (!Serial);

  Serial.println("LoRa Sender");



  if (!LoRa.begin(433E6)) {
    Serial.println("Starting LoRa failed!");
    while (1);
  }
  //LoRa.
  LoRa.setFrequency(433E6);
  LoRa.setSpreadingFactor(7);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setPreambleLength(8);
  LoRa.setCodingRate4(5);//default
  LoRa.setSyncWord(0x12);//default
  LoRa.enableCrc();
}

void loop() {
  Serial.print("Sending packet: ");
  Serial.println(counter);

  // send packet
  
  LoRa.beginPacket();
  LoRa.print("czc-lora");
  //LoRa.print(counter);
  LoRa.endPacket();

  counter++;

  delay(3200);
}