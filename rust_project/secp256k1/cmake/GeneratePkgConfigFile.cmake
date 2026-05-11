# GeneratePkgConfigFile.cmake
# Generate pkg-config file

function(generate_pkg_config_file template_file)
    configure_file(${template_file} ${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}.pc @ONLY)
endfunction()




