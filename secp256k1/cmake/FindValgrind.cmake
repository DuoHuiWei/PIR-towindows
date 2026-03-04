# FindValgrind.cmake
# Simplified FindValgrind module

find_program(VALGRIND_EXECUTABLE valgrind)
if(VALGRIND_EXECUTABLE)
    set(Valgrind_FOUND TRUE)
    set(Valgrind_EXECUTABLE ${VALGRIND_EXECUTABLE})
else()
    set(Valgrind_FOUND FALSE)
endif()




