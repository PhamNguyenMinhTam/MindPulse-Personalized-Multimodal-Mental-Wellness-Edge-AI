idf_component_register(
	SRCS "packet_encoder.cpp" "serial_transport.cpp"
	INCLUDE_DIRS "include"
	REQUIRES esp_driver_uart freertos
)
