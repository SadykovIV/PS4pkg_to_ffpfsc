#pragma once
#define LIBRARY_IMPL (1)
#include <orbis/libkernel.h>
#include <orbis/Sysmodule.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include "printf.h"
#include "libSceAppContent.h"
#include "libSceNpEntitlementAccess.h"

extern int32_t DEBUG_MODE;
extern int32_t addcont_count;
extern dlcldr_struct addcontInfo[SCE_APP_CONTENT_INFO_LIST_MAX_SIZE];

void Logf_i(const char *format, ...);
void Log_i(const char *str);
static int append_to_log_file(const char *str);

#define Logf_if_enabled(...) \
    if (DEBUG_MODE >= 1) \
        Logf_i(__VA_ARGS__);

#define Log_if_enabled(...) \
    if (DEBUG_MODE >= 1) \
        Log_i(__VA_ARGS__);

#define Logf_forced(...) \
    Logf_i(__VA_ARGS__);

#define Log_forced(...) \
    Log_i(__VA_ARGS__);

// int32_t sceSystemServiceLoadExec(const char *path, char *const argv[]);
// no error close: sceSystemServiceLoadExec("exit",0);
