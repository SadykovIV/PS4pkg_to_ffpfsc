#include "common.h"

// injected by main script
int32_t DEBUG_MODE = -1;
int32_t addcont_count = -1;
dlcldr_struct addcontInfo[SCE_APP_CONTENT_INFO_LIST_MAX_SIZE] = {
    {{"0000000000000000"}, 4, {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00}},
};

void Logf_i(const char *format, ...)
{
    char buffer[1024];
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, 1024, format, args);
    va_end(args);
    Log_i(buffer);
}

void Log_i(const char *str)
{
    char *new_str = (char *)malloc(strnlen(str,1024) + 4);
    strcpy(new_str, str);
    strcat(new_str, "\n\0");

    sceKernelDebugOutText(0, new_str);
    append_to_log_file(new_str);
    free(new_str);

    if (DEBUG_MODE == 2)
    {
        OrbisNotificationRequest Buffer;
        memset(&Buffer, 0, sizeof(OrbisNotificationRequest));
        strncpy(Buffer.message, str, 1024);
        Buffer.targetId = -1;

        int res = sceKernelSendNotificationRequest(0, &Buffer, sizeof(Buffer), 0);
    }
}

static int append_to_log_file(const char *str)
{
    int fd = sceKernelOpen("/data/dlcldr.log", SCE_KERNEL_O_WRONLY | SCE_KERNEL_O_CREAT | SCE_KERNEL_O_APPEND, SCE_KERNEL_S_IRWU);

    if (fd <= 0)
    {
        return -1;
    }

    size_t len = strnlen(str, 1024);
    sceKernelWrite(fd, str, len);

    sceKernelClose(fd);

    return 0;
}

#define SCE_SYSMODULE_APP_CONTENT 0x00b4

int32_t _init()
{
	if (DEBUG_MODE >= 1)
	{
		// delete previous log
		sceKernelUnlink("/data/dlcldr.log");
	}

	Log_if_enabled("[dlcldr] init");

	int res = sceSysmoduleLoadModule(SCE_SYSMODULE_APP_CONTENT);

	if (res != SCE_OK)
	{
		// we'll crash so might as well log
		Logf_forced("[dlcldr] sceSysmoduleLoadModule call failed for SCE_SYSMODULE_APP_CONTENT. res: %x", res);
		return -1;
	}

	Log_if_enabled("[dlcldr] loaded libSceAppContent");

	SceAppContentInitParam initParam;
	SceAppContentBootParam bootParam;
	memset(&initParam, 0, sizeof(SceAppContentInitParam));
	memset(&bootParam, 0, sizeof(SceAppContentBootParam));
	res = sceAppContentInitialize(&initParam, &bootParam);

    // SCE_APP_CONTENT_ERROR_BUSY -> already initialized
	if (res < 0 && res != SCE_APP_CONTENT_ERROR_BUSY)
	{
		// we'll crash so might as well log
		Logf_forced("[dlcldr] sceAppContentInitialize call failed. res: %x", res);
		return -1;
	}

	Log_if_enabled("[dlcldr] initialized libSceAppContent");

	return 0;
}

int32_t _fini()
{
	return 0;
}

// from open orbis crtlib.c
extern char __text_start;
void (*__init_array_start[])(void);
void (*__init_array_end[])(void);

// sce_module_param
__asm__(
    ".intel_syntax noprefix \n"
    ".align 0x8 \n"
    ".section \".data.sce_module_param\" \n"
    "_sceProcessParam: \n"
    // size
    "	.quad 	0x18 \n"
    // magic
    "	.quad   0x13C13F4BF \n"
    // SDK version
    "	.quad 	0x1000051 \n"
    ".att_syntax prefix \n");

// data globals
__asm__(
    ".intel_syntax noprefix \n"
    ".align 0x8 \n"
    ".data \n"
    "__dso_handle: \n"
    "	.quad 	0 \n"
    "_sceLibc: \n"
    "	.quad 	0 \n"
    ".att_syntax prefix \n");

// never called, if i put it in init it crashes... works fine without this.
int32_t __attribute__((visibility("hidden"))) module_start(int64_t args, const void* argp)
{
	// Iterate init array and initialize all objects
	for(void(**i)(void) = __init_array_start; i != __init_array_end; i++)
	{
		i[0]();
	}
	return 0;
}

int32_t __attribute__((visibility("hidden"))) module_stop(int64_t args, const void* argp)
{
	return 0;
}