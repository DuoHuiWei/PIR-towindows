# CheckX86_64Assembly.cmake
# Check for x86_64 assembly support

function(check_x86_64_assembly)
    if(CMAKE_SYSTEM_PROCESSOR MATCHES "x86_64|AMD64")
        set(HAVE_X86_64_ASM TRUE PARENT_SCOPE)
    else()
        set(HAVE_X86_64_ASM FALSE PARENT_SCOPE)
    endif()
endfunction()




