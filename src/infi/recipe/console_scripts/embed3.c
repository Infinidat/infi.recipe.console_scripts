#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>
#include <sys/stat.h>
#include <windows.h>
#include <shlwapi.h>

/* For Py_GetArgcArgv(); set by main() */
static char** orig_argv;
static int orig_argc;

/* List of types and defines we use in the code and are declared in the Python include files we don't use */
#ifndef NULL
# define NULL (0)
#endif /* NULL */

#ifndef S_ISDIR
#define S_ISDIR(x) (((x) & S_IFMT) == S_IFDIR)
#endif

/* Since we're only using PyObject as an opaque entity, and always by reference, we declare it as "something". */
typedef void* PyObject;

/* List of functions we'll get from the DLL - see load_python_library() */
void (*__PySys_ResetWarnOptions)(void);
void (*__PySys_SetArgv)(int, wchar_t**);
void (*__Py_SetProgramName)(wchar_t*);
void (*__Py_SetPythonHome)(wchar_t*);
void (*__Py_Initialize)(void);
void (*__Py_Finalize)(void);
void (*__PyErr_Print)(void);
int (*__Py_MakePendingCalls)(void);
int (*__PyModule_AddStringConstant)(PyObject*, const char*, const char*);
int (*__PySys_SetObject)(char* name, PyObject* v);
PyObject* (*__PyImport_AddModule)(const char*);
PyObject* (*__PyUnicode_FromString)(const char*);
int (*__PyRun_SimpleString)(const char*);

void error(const char* fmt, ...){
    va_list args;
    va_start(args, fmt);
    vfprintf(stderr, fmt, args);
    va_end(args);
    fprintf(stderr, "\n");
    exit(1);
}

void posix_error(const char* fmt, ...) {
    va_list args;
    va_start(args, fmt);
    vfprintf(stderr, fmt, args);
    va_end(args);
    fprintf(stderr, " [Errno %d] %s\n", errno, strerror(errno));
    exit(1);
}

void win32_error(const char* fmt, ...) {
    va_list args;

    char* message;
    DWORD error;

    error = GetLastError();
    FormatMessage(FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
                  NULL, error, MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT), (LPSTR) &message, 0, NULL);
    va_start(args, fmt);
    vfprintf(stderr, fmt, args);
    va_end(args);

    fprintf(stderr, " [Win32 error %d] %s\n", error, message);
    LocalFree(message);
    exit(1);
}

void* myalloc(const char* alloc_reason, size_t size) {
    void* result = malloc(size);
    if (result == NULL) {
        posix_error("failed to allocate %s", alloc_reason);
    }
    return result;
}

long get_file_size(FILE* fp) {
    long file_size = -1;
    long cur_pos;

    cur_pos = ftell(fp);
    if (cur_pos == -1) {
        goto error;
    }

    if (fseek(fp, 0, SEEK_END) != 0) {
        goto error;
    }

    file_size = ftell(fp);
    if (file_size == -1) {
        goto error;
    }

    if (fseek(fp, cur_pos, SEEK_SET) != 0) {
        goto error;
    }

    return file_size;

error:
    posix_error("failed to tell file size");
    return -1; /* not used - just to ignore warning */
}

char* read_file(const char* filename) {
    struct stat sb;
    long file_size, bytes_read;
    char* buf;
    FILE* fp;

    if ((fp = fopen(filename, "rb")) == NULL) {
        posix_error("can't open file '%s'", filename);
    }

    /* XXX: does this work on Win/Win64? (see posix_fstat) */
    if (fstat(fileno(fp), &sb) == 0 && S_ISDIR(sb.st_mode)) {
        error("'%s' is a directory, cannot continue");
    }

    file_size = get_file_size(fp);

    buf = (char*) myalloc("file buffer", file_size + 1);

    bytes_read = fread(buf, 1, file_size, fp);
    if (bytes_read != file_size) {
        error("read error from file '%s', read %ld bytes out of %ld", filename, bytes_read, file_size);
    }
    buf[bytes_read] = 0;

    fclose(fp);

    return buf;
}

char* create_script_file_path_from_executable() {
#   define PYTHON_SCRIPT_SUFFIX "-script.py"
    long prefix_len;
    char* script_file_path;
    const char* ext_ptr;
    char filename[MAX_PATH];
    int filename_size;
    filename_size = GetModuleFileNameA(NULL, filename, MAX_PATH);
    filename[filename_size]='\x00';

    ext_ptr = strrchr(filename, '.');
    if (ext_ptr == NULL) {
        /* No extension, so use the entire path. */
        ext_ptr = filename + strlen(filename);
    }

    prefix_len = ext_ptr - filename;
    script_file_path = (char*) myalloc("script file name", prefix_len + strlen(PYTHON_SCRIPT_SUFFIX) + 1);
    strncpy(script_file_path, filename, prefix_len);
    script_file_path[prefix_len] = '\x00';
    strcat(script_file_path, PYTHON_SCRIPT_SUFFIX);

    return script_file_path;
}

char* str_clone(const char* reason, const char* str) {
    char* new_str = myalloc(reason, strlen(str) + 1);
    strcpy(new_str, str);
    return new_str;
}

char* str_back_path(const char* str, char* pos) {
    for (; pos >= str && !(*pos == '\\' || *pos == '/'); --pos)
        ;
    return pos >= str ? pos : NULL;
}

char* find_python_home_from_shebang(const char* filename, char* buffer) {
    char* dir_ptr = NULL;
    char* ptr = buffer;
    char* eol = strchr(buffer, '\n');
    /* This checks if we have a shebang line, also because of short-circuiting it works with a buffer size 0 and 1. */
    if (eol == NULL || ptr[0] != '#' || ptr[1] != '!') {
        error("cannot find shebang line in file '%s'", filename);
    }

    if (*(eol - 1) == '\r') { /* We know eol - ptr > 2 */
        eol--;
    }

    ptr += 2; /* skip the #! */

    /* skip quotes if there are any */
    if (*ptr == '"') {
        ++ptr;
        eol = (char*) memchr(ptr, '"', eol - ptr);
        if (eol == NULL) {
            error("cannot find the end of the quotes ('\"') in the shebang line of file '%s'", filename);
        }
    } else {
        /* find the first space and stop there */
        char* eos = (char*) memchr(ptr, ' ', eol - ptr);
        if (eos != NULL) {
            eol = eos;
        }
    }

    dir_ptr = str_back_path(ptr, eol);
    if (dir_ptr == NULL || dir_ptr == ptr) {
        /* the shebang line was something like: #!python.exe or #!\python.exe */
        return str_clone("python home path", "");
    }

    /* skip the bin/ part of the path */
    dir_ptr = str_back_path(ptr, dir_ptr - 1);
    if (dir_ptr == NULL || dir_ptr == ptr) {
        /* the shebang line was something like: #!bin\python.exe or #!\bin\python.exe */
        return str_clone("python home path", "");
    }

    {
        char* result = (char*) myalloc("python home path", dir_ptr - ptr + 1);
        strncpy(result, ptr, dir_ptr - ptr);
        result[dir_ptr - ptr] = '\x00'; /* always put null at the end because strncpy doesn't necessarily do so */
        return result;
    }
}

void find_dll_function(HMODULE handle, const char* func_name, void** addr) {
    FARPROC proc = GetProcAddress(handle, func_name);
    if (proc == NULL) {
        win32_error("cannot find function '%s' in DLL", func_name);
    }

    *addr = (void*) proc;
}

#define PYTHON_DLL_PATH_PART "\\bin\\python*.dll"
#define PYTHON_EXE_PATH_PART "\\bin\\python.exe"

char* get_python_exe(const char* python_home) {
    char *python_exe_path = myalloc("python exe", MAX_PATH);
    strncpy(python_exe_path, python_home, MAX_PATH);
    strncat(python_exe_path, PYTHON_EXE_PATH_PART, MAX_PATH);
    return python_exe_path;
}

void load_python_library(const char* python_home) {
    HMODULE module;
    HANDLE find_handle;
    WIN32_FIND_DATA find_data;
    char python_dll_path[MAX_PATH];

    strcpy(python_dll_path, python_home);
    strcat(python_dll_path, PYTHON_DLL_PATH_PART);

    find_handle = FindFirstFile(python_dll_path, &find_data);
    if (find_handle == INVALID_HANDLE_VALUE) {
        win32_error("error finding python DLL from '%s'", python_dll_path);
    }
    do {
        strcpy(python_dll_path, python_home);
        strcat(python_dll_path, "\\bin\\");
        strcat(python_dll_path, find_data.cFileName);
        module = LoadLibrary(python_dll_path);
        if (module == NULL) {
            win32_error("error loading python DLL from '%s'", python_dll_path);
        }
    } while (FindNextFile(find_handle, &find_data) != 0);

    FindClose(find_handle);

#   define SET_DLL_FUNC(func) find_dll_function(module, #func, (void**) &__##func)

    SET_DLL_FUNC(PySys_ResetWarnOptions);
    SET_DLL_FUNC(PySys_SetArgv);
    SET_DLL_FUNC(PyErr_Print);
    SET_DLL_FUNC(Py_SetProgramName);
    SET_DLL_FUNC(Py_SetPythonHome);
    SET_DLL_FUNC(Py_Initialize);
    SET_DLL_FUNC(Py_Finalize);
    SET_DLL_FUNC(Py_MakePendingCalls);
    SET_DLL_FUNC(PyModule_AddStringConstant);
    SET_DLL_FUNC(PyImport_AddModule);
    SET_DLL_FUNC(PyRun_SimpleString);
    SET_DLL_FUNC(PySys_SetObject);
    SET_DLL_FUNC(PyUnicode_FromString);

    /* We keep a reference to the DLL open, so it won't get removed. */
}

void fix_dll_search_path(wchar_t* python_home_w) {
    /* Python 3.8 calls LoadLibraryEx with LOAD_LIBRARY_SEARCH_DEFAULT_DIRS
     * which means it also uses LOAD_LIBRARY_SEARCH_USER_DIRS which are
     * directories added by AddDllDirectory. The CRT binaries are currently
     * copied into the bin directory of the actual Python executable which
     * means we need to search there */
    wchar_t python_bin_path_w[MAX_PATH];
    wcsncpy(python_bin_path_w, python_home_w, MAX_PATH);
    wcsncat(python_bin_path_w, L"\\bin", MAX_PATH);
    AddDllDirectory(python_bin_path_w);
}

int WINAPI WinMain(HINSTANCE hI, HINSTANCE hP, LPSTR lpCmd, int nShow) {
    return main(__argc, __argv);
}

int main(int argc, char **argv) {
    int sts;
    char* filename = NULL;
    char* python_home = NULL;
    char* python_exe = NULL;
    char* file_buffer = NULL;
    wchar_t python_home_w[MAX_PATH];
    wchar_t** argv_w = NULL;

    orig_argc = argc;           /* For Py_GetArgcArgv() */
    orig_argv = argv;

    argv_w = CommandLineToArgvW(GetCommandLineW(), &argc);

    filename = create_script_file_path_from_executable();
    file_buffer = read_file(filename);
    python_home = find_python_home_from_shebang(filename, file_buffer);
    python_exe = get_python_exe(python_home);
    mbstowcs(python_home_w, python_home, MAX_PATH);

    load_python_library(python_home);

    fix_dll_search_path(python_home_w);

    (*__PySys_ResetWarnOptions)();

    (*__Py_SetProgramName)(argv_w[0]);

    (*__Py_SetPythonHome)(python_home_w);

    (*__Py_Initialize)();

    (*__PySys_SetArgv)(argc, argv_w);
    (*__PySys_SetObject)("executable", (*__PyUnicode_FromString)(python_exe));

    /* call pending calls like signal handlers (SIGINT) */
    if ((*__Py_MakePendingCalls)() == -1) {
        (*__PyErr_Print)();
        sts = 1;
    } else {
        PyObject* main = (*__PyImport_AddModule)("__main__");
        (*__PyModule_AddStringConstant)(main, "__file__", filename);
        sts = (*__PyRun_SimpleString)(file_buffer) != 0;
    }

    /* Check this environment variable at the end, to give programs the
     * opportunity to set it from Python.
     */

    (*__Py_Finalize)();

    free(python_home);
    free(python_exe);
    free(file_buffer);
    free(filename);

    return sts;
}

/* Make the *original* argc/argv available to other modules.
   This is rare, but it is needed by the secureware extension. */
void Py_GetArgcArgv(int* argc, char*** argv) {
    *argc = orig_argc;
    *argv = orig_argv;
}
