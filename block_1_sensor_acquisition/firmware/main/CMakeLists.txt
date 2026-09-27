idf_component_register(
	SRCS "app_main.cpp" "acquisition_tasks.cpp"
	INCLUDE_DIRS "."
	REQUIRES acquisition inmp441 max30102 transport esp_timer esp_system
)
