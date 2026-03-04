# CheckArm32Assembly.cmake
# Check for ARM32 assembly support

function(check_arm32_assembly)
    if(CMAKE_SYSTEM_PROCESSOR MATCHES "ARM|arm")
        set(HAVE_ARM32_ASM TRUE PARENT_SCOPE)
    else()
        set(HAVE_ARM32_ASM FALSE PARENT_SCOPE)
    endif()
endfunction()




