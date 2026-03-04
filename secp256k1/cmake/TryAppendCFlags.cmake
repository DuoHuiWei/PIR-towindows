# TryAppendCFlags.cmake
# Helper function to try appending compiler flags

include(CheckCCompilerFlag)

function(try_append_c_flags flag)
    string(REPLACE " " ";" flag_list "${flag}")
    foreach(f ${flag_list})
        # Create a unique variable name for this flag
        string(MAKE_C_IDENTIFIER "FLAG_${f}" flag_var)
        check_c_compiler_flag("${CMAKE_C_FLAGS} ${f}" ${flag_var})
        if(${flag_var})
            set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${f}" PARENT_SCOPE)
        endif()
    endforeach()
endfunction()

