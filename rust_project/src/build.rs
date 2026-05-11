
use std::env;

fn main()
{
    println!("cargo:rerun-if-changed=utils/helper.cpp");

    let target = env::var("TARGET").unwrap_or_default();
    let target_os = env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
    let target_env = env::var("CARGO_CFG_TARGET_ENV").unwrap_or_default();
    let is_windows = target_os == "windows";
    let is_msvc = target_env == "msvc";
    let arch = env::consts::ARCH;

    // 检查目标平台：项目使用 MinGW + CMake，不支持 MSVC 目标
    if is_windows && is_msvc {
        eprintln!("错误: 检测到 MSVC 目标平台 ({})", target);
        eprintln!("此项目使用 MinGW + CMake，需要切换到 MinGW 目标平台。");
        eprintln!("");
        eprintln!("请执行以下命令切换到 MinGW 目标平台:");
        eprintln!("  rustup target add x86_64-pc-windows-gnu");
        eprintln!("  cargo build --release --target x86_64-pc-windows-gnu");
        eprintln!("");
        eprintln!("或者设置默认目标平台:");
        eprintln!("  rustup default nightly-2023-09-24-x86_64-pc-windows-gnu");
        eprintln!("");
        panic!("不支持的编译目标平台: {}", target);
    }

    // 设置 C++ 编译器（MinGW 或 Linux）
    env::set_var("CXX", "g++");
    
    // MSVC 相关代码已注释（项目使用 MinGW + CMake）
    // if is_windows {
    //     if is_msvc {
    //         // MSVC 环境 - 不设置 CXX，让 cc crate 自动检测
    //         // MSVC 使用 /openmp 而不是 -fopenmp
    //     } else {
    //         // MinGW 环境
    //         env::set_var("CXX", "g++");
    //     }
    // } else {
    //     env::set_var("CXX", "g++");
    // }

    // 确定 secp256k1 库路径（MinGW/Linux 使用 .libs 目录）
    let current_dir = env::current_dir().expect("error get directory");
    let secp256k1_lib_path = current_dir.join("secp256k1").join(".libs");
    
    // MSVC 路径处理已注释（项目使用 MinGW + CMake）
    // let secp256k1_lib_path = if is_windows && is_msvc {
    //     // MSVC 构建的库通常在 build/lib/Release 或 build/lib
    //     // 优先尝试 Release 目录，如果不存在则使用 build/lib
    //     let release_path = current_dir.join("secp256k1").join("build").join("lib").join("Release");
    //     if release_path.exists() {
    //         release_path
    //     } else {
    //         current_dir.join("secp256k1").join("build").join("lib")
    //     }
    // } else {
    //     // MinGW/Linux 使用 .libs 目录
    //     current_dir.join("secp256k1").join(".libs")
    // };

    if arch == "x86_64" // server arch
    {
        let mut build = cc::Build::new();
        build.cpp(true)
            .file("utils/helper.cpp")
            .include("secp256k1/include")  // 添加 secp256k1 头文件路径
            .define("SECP256K1_STATIC", None);  // 定义静态库宏
        
        // GCC/Clang 特定的警告标志
        build.flag("-Wno-unused-function")
            .flag("-Wno-unused-result");

        if is_windows {
            // MinGW 编译选项
            build.flag("-fopenmp")
                .flag("-mavx2")
                .flag("-no-pie")
                .compile("helper");
            println!("cargo:rustc-link-lib=gomp");  // MinGW OpenMP 库
        } else {
            // Linux/Unix
            build.flag("-fopenmp")
                .flag("-mavx2")
                .flag("-no-pie")
                .compile("helper");
            println!("cargo:rustc-link-lib=gomp");
        }
        
        // MSVC 编译选项已注释（项目使用 MinGW + CMake）
        // if is_windows {
        //     if is_msvc {
        //         // MSVC 编译选项
        //         // cc crate 在 Windows MSVC 上会自动检测编译器
        //         // 使用 MSVC 风格的标志
        //         build.define("_OPENMP", None)
        //             .flag("/openmp")  // MSVC 的 OpenMP 标志
        //             .flag("/arch:AVX2");  // MSVC 的 AVX2 标志
        //         // 移除 GCC 特定的警告标志（MSVC 不支持）
        //         build.compile("helper");
        //         println!("cargo:rustc-link-lib=vcomp");  // MSVC OpenMP 库
        //     } else {
        //         // MinGW 编译选项
        //         build.flag("-fopenmp")
        //             .flag("-mavx2")
        //             .flag("-no-pie")
        //             .compile("helper");
        //         println!("cargo:rustc-link-lib=gomp");  // MinGW OpenMP 库
        //     }
        // } else {
        //     // Linux/Unix
        //     build.flag("-fopenmp")
        //         .flag("-mavx2")
        //         .flag("-no-pie")
        //         .compile("helper");
        //     println!("cargo:rustc-link-lib=gomp");
        // }

        // Link with the secp256k1 library and specify the search path
        println!("cargo:rustc-link-lib=static=secp256k1");
        println!("cargo:rustc-link-search=native={}", secp256k1_lib_path.display());
        println!("cargo:warning=secp256k1 library path: {}", secp256k1_lib_path.display());
    }
    else
    {
        let mut build = cc::Build::new();
        build.cpp(true)
            .file("utils/helper.cpp")
            .include("secp256k1/include")  // 添加 secp256k1 头文件路径
            .define("SECP256K1_STATIC", None);  // 定义静态库宏
        
        // GCC/Clang 特定的警告标志
        build.flag("-Wno-unused-function");
        
        build.compile("helper");
        
        // MSVC 相关代码已注释（项目使用 MinGW + CMake）
        // if !is_msvc {
        //     build.flag("-Wno-unused-function");
        // }

        // Link with the secp256k1 library and specify the search path
        // 注意：链接顺序很重要，secp256k1 必须在 helper 之后链接
        println!("cargo:rustc-link-search=native={}", secp256k1_lib_path.display());
        println!("cargo:rustc-link-lib=static=secp256k1");
        println!("cargo:warning=secp256k1 library path: {}", secp256k1_lib_path.display());
    }
}
