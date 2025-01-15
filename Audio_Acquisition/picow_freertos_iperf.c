#include "pico/cyw43_arch.h"
#include "pico/stdlib.h"
#include "hardware/dma.h"
#include "hardware/adc.h"
#include "hardware/irq.h"
 
#include "lwip/apps/lwiperf.h"
#include "lwip/ip4_addr.h"
#include "lwip/netif.h"
#include "lwip/sockets.h"
 
#include "FreeRTOS.h"
#include "task.h"

#define TEST_LED 7
#define PORT 12345
#define client_IP "192.168.137.1"

#define ADC_CHAN 0
#define ADC_PIN 26
// Number of samples for one Transfer
#define NUM_SAMPLES 2048
// Sample rate (Hz)
#define Fs 16000.0
// ADC clock rate (unmutable!)
#define ADCCLK 48000000.0


// Here's where we'll have the DMA channel put ADC samples
uint8_t sample_array_1[NUM_SAMPLES];
uint8_t sample_array_2[NUM_SAMPLES];
uint8_t *buffers[] = { sample_array_1, sample_array_2 }; 
uint8_t buff_num = 0;

// Pointer to address of start of sample buffer
uint8_t * sample_address_pointer = &sample_array_1[0];

// DMA channels for sampling ADC
int sample_chan;
int control_chan;



static void main_task() {
	// Initialize stdio
	//stdio_init_all();

	// Init GPIO for analogue use
	adc_gpio_init(ADC_PIN);
	
	// Initialize the ADC harware
	// (resets it, enables the clock, spins until the hardware is ready)
	adc_init();
	
	// Select analog mux input (0...3 are GPIO 26, 27, 28, 29; 4 is temp sensor)
	adc_select_input(ADC_CHAN);
	
	// Setup the FIFO
	adc_fifo_setup(
	    true,    // Write each completed conversion to the sample FIFO
		true,    // Enable DMA data request (DREQ)
		1,       // DREQ (and IRQ) asserted when at least 1 sample present
		false,   // We won't see the ERR bit because of 8 bit reads; disable.
		true     // Shift each sample to 8 bits when pushing to FIFO
	);

	// This is setup to grab a sample at 16kHz
	adc_set_clkdiv(ADCCLK / Fs);
	
	//>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
	
	// ADC DMA CONFIGURATION
	sample_chan = dma_claim_unused_channel(true);
	
	// Channel configurations
	dma_channel_config c2 = dma_channel_get_default_config(sample_chan);
	
	// Reading from constant address, writing to incrementing byte addresses
	channel_config_set_transfer_data_size(&c2, DMA_SIZE_8);
	channel_config_set_read_increment(&c2, false);
	channel_config_set_write_increment(&c2, true);
	
	// Pace transfers based on availability of ADC samples
	channel_config_set_dreq(&c2, DREQ_ADC);
	
	// Configure the channel
	dma_channel_configure(sample_chan, // ADC DMA Channel
		&c2,            // channel config
		sample_array_1,   // dst
		&adc_hw->fifo,  // src
		NUM_SAMPLES,    // transfer count
		false           // don't start immediately
	);

	// CONTROL CHANNEL
	control_chan = dma_claim_unused_channel(true);
	
	// Channel configurations
	dma_channel_config c3 = dma_channel_get_default_config(control_chan);
	
	// Reading from constant address, writing to constant address
	channel_config_set_transfer_data_size(&c3, DMA_SIZE_32); // 32-bit txfers
	channel_config_set_read_increment(&c3, false); // no read incrementing
	channel_config_set_write_increment(&c3, false); // no write incrementing
	channel_config_set_chain_to(&c3, sample_chan); // chain to sample chan
	//When this channel(control_chan) completes, it will trigger the sample_chan

	// Configure the channel
	dma_channel_configure(
	    control_chan,                         // Channel to be configured
		&c3,                                  // The configuration we just created
		&dma_hw->ch[sample_chan].write_addr,  // Write address (channel 0 read address)
		&sample_address_pointer,              // Read address (POINTER TO AN ADDRESS)
		1,                                    // Number of transfers, in this case each is 4 byte
		false                                 // Don't start immediately.
	);
	
	//>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
	
	// Initializing TEST LED
	gpio_init(TEST_LED);
	gpio_set_dir(TEST_LED, GPIO_OUT);
	
	// Initialize the CYW43 architecture(WIFI chip)
	if (cyw43_arch_init())
	{
		printf("failed to initialise\n");
		return;
	}
	
	// Enables the Wi - Fi in Station mode to get connected to other Wi - Fi Access Points
	cyw43_arch_enable_sta_mode();
 
	printf("Connecting to WiFi...\n");
 
	// Connect to a wireless access point, blocking until the network is joined or a failure is detected.
	// const char * WIFI_SSID = "GEMY";
	// const char * WIFI_PASSWORD = "00000000";
	if (cyw43_arch_wifi_connect_blocking(WIFI_SSID, WIFI_PASSWORD, CYW43_AUTH_WPA2_MIXED_PSK)) {
		printf("failed to connect.\n");
		return;
	}
	else printf("Connected.\n");
	
	printf("Creating socket...\n");
	
	// Declaring Socket Address and file descriptor Variables
	int server_fd;
	struct sockaddr_in client_addr;
	
	// Creating UDP socket
	server_fd = socket(AF_INET, SOCK_DGRAM, 0);
    
	//Preparing address of client we will send to
	client_addr.sin_family = AF_INET; // For the internet address family
	client_addr.sin_port = htons(PORT); // Assign port number
	client_addr.sin_addr.s_addr = inet_addr(client_IP); // Assign client ip
	
	// Check if socket was created successfully
	if (server_fd < 0) {
		printf("Unable to create socket!\n");
		return;
	}
	else printf("Socket done...\n");
	
	//>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
	
	// Start streaming......
	gpio_put(TEST_LED, 1);
	printf("Starting capture\n");
	
	// Start the ADC channel
	dma_start_channel_mask((1u << sample_chan));
	
	// Start the ADC
	adc_run(true);
	
	printf("Start sending...\n");
	while (true)
	{
		// Wait for NUM_SAMPLES samples to be gathered
		dma_channel_wait_for_finish_blocking(sample_chan);
		
		if (sample_address_pointer == &sample_array_1[0])
		{
			sample_address_pointer = &sample_array_2[0];
		}
		else
		{
			sample_address_pointer = &sample_array_1[0];
		}
		
		// Restart the sample channel with control_chan
		dma_channel_start(control_chan);
		
		// Send audio chunk
		sendto(server_fd, buffers[buff_num], NUM_SAMPLES, 0, (const struct sockaddr *)&client_addr, sizeof(client_addr));
		
		buff_num = (buff_num + 1) % 2;
		
		
	}
	cyw43_arch_deinit();
}
 
int main(void)
{
	// Initialize all of the present standard stdio types
	stdio_init_all();
	
	// Create task so that scheduler can handle it
	xTaskCreate(main_task, "MainThread", configMINIMAL_STACK_SIZE, NULL, 2, NULL);
	
	// Wait for some seconds so you can notice the printing of messages on serial monitor
	// sleep_ms(5000);
	
	// Start FreeRTOS scheduler
	vTaskStartScheduler();
	return 0;
}