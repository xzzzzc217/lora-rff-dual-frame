#include "LoRaWan_APP.h"
#include "Arduino.h"

#define RF_FREQUENCY                                510000000 // Hz
#define TX_OUTPUT_POWER                             17        // dBm
#define LORA_BANDWIDTH                              0         // [0: 125 kHz, 1: 250 kHz, 2: 500 kHz, 3: Reserved]
#define LORA_SPREADING_FACTOR                       7         // [SF7..SF12]
#define LORA_CODINGRATE                             1         // [1: 4/5, 2: 4/6, 3: 4/7, 4: 4/8]
#define LORA_PREAMBLE_LENGTH                        8         // Same for Tx and Rx
#define LORA_SYMBOL_TIMEOUT                         0         // Symbols
#define LORA_FIX_LENGTH_PAYLOAD_ON                  false
#define LORA_IQ_INVERSION_ON                        false

#define RX_TIMEOUT_VALUE                            1000
#define BUFFER_SIZE                                 30 // Define the payload size here

char txpacket[BUFFER_SIZE];
char rxpacket[BUFFER_SIZE];

double txNumber;
int counter = 0;
bool lora_idle = true;

static RadioEvents_t RadioEvents; 
void OnTxDone(void);
void OnTxTimeout(void);

enum TxPairState { 
    READY,       // 准备发送一组中的第一帧
    FIRST_SENT,  // 第一帧已发送，等待30ms后发送第二帧
    SECOND_SENT  // 第二帧已发送，等待150ms后开始下一组
};

TxPairState txState = READY;
unsigned long lastTxTimestamp = 0;

void setup() {
    Serial.begin(9600);
    Mcu.begin(HELTEC_WIFI_LORA_32_V3, 0); // 适用于Heltec ESP32 LoRa 32开发板
    
    txNumber = 0;

    RadioEvents.TxDone = OnTxDone;
    RadioEvents.TxTimeout = OnTxTimeout;
    
    Radio.Init(&RadioEvents);
    Radio.SetChannel(RF_FREQUENCY);
    Radio.SetTxConfig(MODEM_LORA, TX_OUTPUT_POWER, 0, LORA_BANDWIDTH,
                      LORA_SPREADING_FACTOR, LORA_CODINGRATE,
                      LORA_PREAMBLE_LENGTH, LORA_FIX_LENGTH_PAYLOAD_ON,
                      true, 0, 0, LORA_IQ_INVERSION_ON, 3000); 
}

void loop() {
    Radio.IrqProcess();
    
    if (lora_idle) {
        unsigned long currentTime = millis();
        if (txState == READY) {
            // 发送第一帧
            Serial.print("Sending first frame at ");
            Serial.println(currentTime);
            sprintf(txpacket, "czc-lora");
            Radio.Send((uint8_t *)txpacket, strlen(txpacket));
            lora_idle = false;
            txState = FIRST_SENT;
            lastTxTimestamp = currentTime;
        }
        else if (txState == FIRST_SENT) {
            if (currentTime - lastTxTimestamp >= 30) {
                // 发送第二帧
                Serial.print("Sending second frame at ");
                Serial.println(currentTime);
                Serial.print("Interval from first frame: ");
                Serial.println(currentTime - lastTxTimestamp);
                sprintf(txpacket, "czc-lora");
                Radio.Send((uint8_t *)txpacket, strlen(txpacket));
                lora_idle = false;
                txState = SECOND_SENT;
                lastTxTimestamp = currentTime;
            }
        }
        else if (txState == SECOND_SENT) {
            if (currentTime - lastTxTimestamp >= 150) {
                // 下一组双帧发送准备就绪
                Serial.print("Ready for next pair at ");
                Serial.println(currentTime);
                Serial.print("Interval from second frame: ");
                Serial.println(currentTime - lastTxTimestamp);
                txState = READY;
            }
        }
    }
}

void OnTxDone(void) {
    unsigned long doneTime = millis();
    if (txState == FIRST_SENT) {
        Serial.print("First frame finished sending at ");
        Serial.println(doneTime);
    }
    else if (txState == SECOND_SENT) {
        Serial.print("Second frame finished sending at ");
        Serial.println(doneTime);
    }
    lora_idle = true;
}

void OnTxTimeout(void) {
    Radio.Sleep();
    Serial.println("TX Timeout......");
    lora_idle = true;
}