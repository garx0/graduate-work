project(delaytool)

set(CMAKE_CXX_STANDARD 17)
add_definitions(-O2)
add_definitions(-Wall)
#add_definition(-Werror)

add_library(tinyxml2 STATIC source/tinyxml2/tinyxml2.cpp)

add_executable(delaytool source/main.cpp source/algo.cpp source/configio.cpp source/delay.cpp)
target_link_libraries(delaytool tinyxml2)

add_executable(deletepaths source/deletepaths.cpp source/configio.cpp source/algo.cpp source/delay.cpp)
target_link_libraries(deletepaths tinyxml2)
