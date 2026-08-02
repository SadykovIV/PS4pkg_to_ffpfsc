#include "common.h"

int32_t dlcldr_sceAppContentInitialize(
	SceAppContentInitParam *initParam,
	SceAppContentBootParam *bootParam)
{
	Log_if_enabled("[dlcldr] dlcldr_sceAppContentInitialize called");
	return 0;
}

int32_t dlcldr_sceAppContentAppParamGetInt(
	SceAppContentAppParamId paramId,
	int32_t *value)
{
	// patch trial flag
	if (paramId == SCE_APP_CONTENT_APPPARAM_ID_SKU_FLAG)
	{
		Log_if_enabled("[dlcldr] dlcldr_sceAppContentAppParamGetInt called for SKU_FLAG, returning FULL");
		*value = SCE_APP_CONTENT_APPPARAM_SKU_FLAG_FULL;
		return 0;
	}

	Log_if_enabled("[dlcldr] dlcldr_sceAppContentAppParamGetInt called");
	return sceAppContentAppParamGetInt(paramId, value);
}

int32_t dlcldr_sceAppContentGetAddcontInfoList(
	SceNpServiceLabel serviceLabel,
	SceAppContentAddcontInfo *list,
	uint32_t listNum,
	uint32_t *hitNum)
{
	Logf_if_enabled("[dlcldr] dlcldr_sceAppContentGetAddcontInfoList called");

	if (listNum == 0 || list == NULL)
	{
		if (hitNum == NULL)
		{
			Logf_if_enabled("[dlcldr] dlcldr_sceAppContentGetAddcontInfoList: list is null or listNum is 0, hitNum is NULL");
			return SCE_APP_CONTENT_ERROR_PARAMETER;
		}
		*hitNum = addcont_count;
		Logf_if_enabled("[dlcldr] sceNpEntitlementAccessGetAddcontEntitlementInfoList: list is null or listNum is 0, hitNum set to %d", addcont_count);
		return SCE_OK;
	}

	int dlcsToList = addcont_count < listNum ? addcont_count : listNum;

	for (int i = 0; i < dlcsToList; i++)
	{
		strncpy(list[i].entitlementLabel.data, addcontInfo[i].entitlementLabel, SCE_NP_UNIFIED_ENTITLEMENT_LABEL_SIZE);
		list[i].status = addcontInfo[i].status;
	}

	if (hitNum != NULL)
	{
		*hitNum = dlcsToList;
	}

	Logf_if_enabled("[dlcldr] dlcldr_sceAppContentGetAddcontInfoList: returning %d dlcs", dlcsToList);
	return SCE_OK;
}

int32_t dlcldr_sceAppContentGetAddcontInfo(
	SceNpServiceLabel serviceLabel,
	const SceNpUnifiedEntitlementLabel *entitlementLabel,
	SceAppContentAddcontInfo *info)
{
	Logf_if_enabled("[dlcldr] dlcldr_sceAppContentGetAddcontInfo called for %s", entitlementLabel->data);

	if (entitlementLabel == NULL || info == NULL)
	{ 
		Logf_if_enabled("[dlcldr] dlcldr_sceAppContentGetAddcontInfo failed, info or label is NULL");
		return SCE_APP_CONTENT_ERROR_PARAMETER; 
	}
	
	for (int i = 0; i < addcont_count; i++)
	{
		if (strncmp(entitlementLabel->data, addcontInfo[i].entitlementLabel, SCE_NP_UNIFIED_ENTITLEMENT_LABEL_SIZE-1))
		{ continue; }

		Logf_if_enabled("[dlcldr] dlcldr_sceAppContentGetAddcontInfo found %s", entitlementLabel->data);
			
		strncpy(info->entitlementLabel.data, addcontInfo[i].entitlementLabel, SCE_NP_UNIFIED_ENTITLEMENT_LABEL_SIZE);
		info->status = addcontInfo[i].status;
		return 0;
	}

	Logf_if_enabled("[dlcldr] dlcldr_sceAppContentGetAddcontInfo did not find %s, returning SCE_APP_CONTENT_ERROR_DRM_NO_ENTITLEMENT", entitlementLabel->data);

	return SCE_APP_CONTENT_ERROR_DRM_NO_ENTITLEMENT;
}

int32_t dlcldr_sceAppContentGetEntitlementKey(
	SceNpServiceLabel serviceLabel,
	const SceNpUnifiedEntitlementLabel *entitlementLabel,
	SceAppContentEntitlementKey *key)
{
	Logf_if_enabled("[dlcldr] dlcldr_sceAppContentGetEntitlementKey called for %s", entitlementLabel->data);

	if (entitlementLabel == NULL || key == NULL)
	{ 
		Logf_if_enabled("[dlcldr] dlcldr_sceAppContentGetEntitlementKey failed, key or label is NULL");
		return SCE_APP_CONTENT_ERROR_PARAMETER; 
	}

	for (int i = 0; i < addcont_count; i++)
	{
		if (strncmp(entitlementLabel->data, addcontInfo[i].entitlementLabel, SCE_NP_UNIFIED_ENTITLEMENT_LABEL_SIZE-1))
		{ continue; }

		Logf_if_enabled("[dlcldr] dlcldr_sceAppContentGetEntitlementKey found key for %s", entitlementLabel->data);
		
		memcpy(key->data, addcontInfo[i].key, SCE_APP_CONTENT_ENTITLEMENT_KEY_SIZE);
		return 0;
		
	}

	Logf_if_enabled("[dlcldr] dlcldr_sceAppContentGetEntitlementKey did not find key for %s, returning SCE_APP_CONTENT_ERROR_DRM_NO_ENTITLEMENT", entitlementLabel->data);

	return SCE_APP_CONTENT_ERROR_DRM_NO_ENTITLEMENT;
}

int32_t dlcldr_sceAppContentAddcontDelete(
	SceNpServiceLabel serviceLabel,
	const SceNpUnifiedEntitlementLabel *entitlementLabel)
{
	return 0;
}

int32_t dlcldr_sceAppContentAddcontMount(
	SceNpServiceLabel serviceLabel,
	const SceNpUnifiedEntitlementLabel *entitlementLabel,
	SceAppContentMountPoint *mountPoint)
{
	// checked and originally it returns SCE_APP_CONTENT_ERROR_NOT_FOUND
	// both if is without data and if the entitlementLabel is not found

	Logf_if_enabled("[dlcldr] dlcldr_sceAppContentAddcontMount called for %s", entitlementLabel->data);

	for (int i = 0; i < addcont_count; i++)
	{
		if (strncmp(entitlementLabel->data, addcontInfo[i].entitlementLabel, SCE_NP_UNIFIED_ENTITLEMENT_LABEL_SIZE-1))
		{ continue; }
		
		if (addcontInfo[i].status != SCE_APP_CONTENT_ADDCONT_DOWNLOAD_STATUS_INSTALLED)
		{
			Logf_if_enabled("[dlcldr] dlcldr_sceAppContentAddcontMount failed for %s, not installed", entitlementLabel->data);
			return SCE_APP_CONTENT_ERROR_NOT_FOUND;
		}

		// the asm handler uses 2 digits for less code
		// and also to avoid changing the naming convention
		snprintf(mountPoint->data, SCE_APP_CONTENT_MOUNTPOINT_DATA_MAXSIZE, "/app0/dlc%02d", i);

		Logf_if_enabled("[dlcldr] dlcldr_sceAppContentAddcontMount mounted %s at %s", entitlementLabel->data, mountPoint->data);
		return 0;
		
	}

	Logf_if_enabled("[dlcldr] dlcldr_sceAppContentAddcontMount failed for %s, not found", entitlementLabel->data);

	return SCE_APP_CONTENT_ERROR_NOT_FOUND;
}

int32_t dlcldr_sceAppContentAddcontUnmount(
	const SceAppContentMountPoint *mountPoint)
{
	return 0;
}

int32_t dlcldr_sceAppContentGetPftFlag(
	SceAppContentPftFlag *pftFlag)
{
	*pftFlag = SCE_APP_CONTENT_PFT_FLAG_OFF;
	return 0;
}

// typedef enum SceNpState
// {
// 	SCE_NP_STATE_UNKNOWN = 0,
// 	SCE_NP_STATE_SIGNED_OUT,
// 	SCE_NP_STATE_SIGNED_IN
// } SceNpState;
// int sceNpGetState(
// 		SceUserServiceUserId userId,
// 		SceNpState *state);
// int (*sceNpGetState)(SceUserServiceUserId userId, SceNpState *state) = NULL;

// gYOLMIKifpk
// int32_t dlcldr_sceNpGetState(
// 	SceUserServiceUserId userId,
// 	SceNpState *state)
// {
// 	*state = SCE_NP_STATE_SIGNED_IN;
// 	if (DEBUG_MODE != 0)
// 	{
// 		Log("[dlcldr] sceNpGetState faked signed_in");
// 	}
// 	return 0;
// }

// int32_t dlcldr_sceAppContentAppParamGetInt(
// 	SceAppContentAppParamId paramId,
// 	int32_t *value)
// {
// 	return 0;
// }

// int32_t dlcldr_sceAppContentAddcontEnqueueDownload(
// 	SceNpServiceLabel serviceLabel,
// 	const SceNpUnifiedEntitlementLabel *entitlementLabel)
// {
// 	return 0;
// }

// int32_t dlcldr_sceAppContentTemporaryDataMount2(
// 	SceAppContentTemporaryDataOption option,
// 	SceAppContentMountPoint *mountPoint)
// {
// 	return 0;
// }

// int32_t dlcldr_sceAppContentTemporaryDataUnmount(
// 	const SceAppContentMountPoint *mountPoint)
// {
// 	return 0;
// }

// int32_t dlcldr_sceAppContentTemporaryDataFormat(
// 	const SceAppContentMountPoint *mountPoint)
// {
// 	return 0;
// }

// int32_t dlcldr_sceAppContentTemporaryDataGetAvailableSpaceKb(
// 	const SceAppContentMountPoint *mountPoint,
// 	size_t *availableSpaceKb)
// {
// 	return 0;
// }

// int32_t dlcldr_sceAppContentDownloadDataFormat(
// 	const SceAppContentMountPoint *mountPoint)
// {
// 	return 0;
// }

// int32_t dlcldr_sceAppContentDownloadDataGetAvailableSpaceKb(
// 	const SceAppContentMountPoint *mountPoint,
// 	size_t *availableSpaceKb)
// {
// 	return 0;
// }

// int32_t dlcldr_sceAppContentGetAddcontDownloadProgress(
// 	SceNpServiceLabel serviceLabel,
// 	const SceNpUnifiedEntitlementLabel *entitlementLabel,
// 	SceAppContentAddcontDownloadProgress *progress)
// {
// 	return 0;
// }

// int32_t dlcldr_sceAppContentAddcontEnqueueDownloadByEntitlemetId() { return 0; }
// int32_t dlcldr_sceAppContentAddcontEnqueueDownloadSp() { return 0; }
// int32_t dlcldr_sceAppContentAddcontMountByEntitlemetId() { return 0; }
// int32_t dlcldr_sceAppContentAddcontShrink() { return 0; }
// int32_t dlcldr_sceAppContentAppParamGetString() { return 0; }
// int32_t dlcldr_sceAppContentDownload0Expand() { return 0; }
// int32_t dlcldr_sceAppContentDownload0Shrink() { return 0; }
// int32_t dlcldr_sceAppContentDownload1Expand() { return 0; }
// int32_t dlcldr_sceAppContentDownload1Shrink() { return 0; }
// int32_t dlcldr_sceAppContentGetAddcontInfoByEntitlementId() { return 0; }
// int32_t dlcldr_sceAppContentGetAddcontInfoListByIroTag() { return 0; }
// int32_t dlcldr_sceAppContentGetDownloadedStoreCountry() { return 0; }
// int32_t dlcldr_sceAppContentGetEntitlementKey() { return 0; }
// int32_t dlcldr_sceAppContentGetPftFlag() { return 0; }
// int32_t dlcldr_sceAppContentGetRegion() { return 0; }
// int32_t dlcldr_sceAppContentRequestPatchInstall() { return 0; }
// int32_t dlcldr_sceAppContentSmallSharedDataFormat() { return 0; }
// int32_t dlcldr_sceAppContentSmallSharedDataGetAvailableSpaceKb() { return 0; }
// int32_t dlcldr_sceAppContentSmallSharedDataMount() { return 0; }
// int32_t dlcldr_sceAppContentSmallSharedDataUnmount() { return 0; }
