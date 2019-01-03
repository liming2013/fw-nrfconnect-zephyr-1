# Build a second bootloader image
 zephyr_add_multi_image()
add_subdirectory("${CONFIG_MCUBOOT_CMAKELISTS_DIR}" ${CMAKE_CURRENT_BINARY_DIR}/mcuboot)
