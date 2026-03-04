# CheckStringOptionValue.cmake
# Helper function to validate string option values

function(check_string_option_value option_name)
    get_property(option_strings CACHE ${option_name} PROPERTY STRINGS)
    get_property(option_value CACHE ${option_name} PROPERTY VALUE)
    
    if(option_strings)
        list(FIND option_strings "${option_value}" index)
        if(index EQUAL -1)
            message(FATAL_ERROR 
                "Invalid value '${option_value}' for option ${option_name}.\n"
                "Valid values are: ${option_strings}")
        endif()
    endif()
endfunction()




