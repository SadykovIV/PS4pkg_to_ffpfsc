#include "common.h"

int32_t sceNpEntitlementAccessAbortRequest(int64_t requestId) { return SCE_OK; }
int32_t sceNpEntitlementAccessDeleteRequest(int64_t requestId) { return SCE_OK; }
int32_t sceNpEntitlementAccessGenerateTransactionId(SceNpEntitlementAccessTransactionId *transactionId)
{
	Logf_if_enabled("[dlcldr] sceNpEntitlementAccessGenerateTransactionId called");
	if (transactionId == NULL)
	{
		Logf_if_enabled("[dlcldr] sceNpEntitlementAccessGenerateTransactionId: transactionId is null");
		return SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER;
	}
	// i tested the real function, it returns this format, idk why the buffer is 65 bytes
	strncpy(transactionId->transactionId, "00000000-0000-0000-0000-000000000000", SCE_NP_ENTITLEMENT_ACCESS_TRANSACTION_ID_MAX_SIZE);
	Log_if_enabled("[dlcldr] sceNpEntitlementAccessGenerateTransactionId: returning dummy transactionId & SCE_OK");
	return SCE_OK;
}

int32_t sceNpEntitlementAccessGetAddcontEntitlementInfo(
	SceNpServiceLabel serviceLabel,
	const SceNpUnifiedEntitlementLabel *entitlementLabel,
	SceNpEntitlementAccessAddcontEntitlementInfo *info)
{
	// results from the real function
	// returns SCE_NP_ENTITLEMENT_ACCESS_ERROR_NO_ENTITLEMENT for unknown entitlementlabel
	// returns SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER is info is null, it checks this before the entitlementlabel

	Logf_if_enabled("[dlcldr] sceNpEntitlementAccessGetAddcontEntitlementInfo called for %s", entitlementLabel->data);
	if (info == NULL)
	{
		Log_if_enabled("[dlcldr] sceNpEntitlementAccessGetAddcontEntitlementInfo: info is null, returning SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER");
		return SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER;
	}

	for (int i = 0; i < addcont_count; i++)
	{
		if (strncmp(entitlementLabel->data, addcontInfo[i].entitlementLabel, SCE_NP_UNIFIED_ENTITLEMENT_LABEL_SIZE-1))
		{ continue; }
		
		strncpy(info->entitlementLabel.data, addcontInfo[i].entitlementLabel, SCE_NP_UNIFIED_ENTITLEMENT_LABEL_SIZE);
		info->downloadStatus = addcontInfo[i].status;
		info->packageType = addcontInfo[i].status == 4 ? SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSAC : SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSAL;
		Logf_if_enabled("[dlcldr] sceNpEntitlementAccessGetAddcontEntitlementInfo found %s", entitlementLabel->data);
		return SCE_OK;
	}

	Logf_if_enabled("[dlcldr] sceNpEntitlementAccessGetAddcontEntitlementInfo did not find %s, returning SCE_NP_ENTITLEMENT_ACCESS_ERROR_NO_ENTITLEMENT", entitlementLabel->data);
	return SCE_NP_ENTITLEMENT_ACCESS_ERROR_NO_ENTITLEMENT;
}


// not part of ps4 sdk 8.00 stub
// also not there in https://github.com/idc/ps4libdoc/blob/9.00/system/common/lib/libSceNpEntitlementAccess.sprx.json
// so this could be ignored
int32_t sceNpEntitlementAccessGetAddcontEntitlementInfoIndividual()
{
	// i couldnt figure out what this function is for

	// ida:
	// sceNpEntitlementAccessGetAddcontEntitlementInfoIndividual(unsigned int a1, unsigned int a2, __int64 a3, __int64 a4)

	// for testing i was assuming these parameters
	// int32_t sceNpEntitlementAccessGetAddcontEntitlementInfoIndividual(
	// 		SceUserServiceUserId userId,
	// 		SceNpServiceLabel 					serviceLabel,
	// 		const SceNpUnifiedEntitlementLabel	*entitlementLabel,
	// 		SceNpEntitlementAccessAddcontEntitlementInfo	*info
	// )

	// my first thought was that the frist/second parameter is the userid, since in ida it shows up as uint for other functions too
	// but it didnt work, tried swapping the order of the first two parameters, still didnt work
	// it returns SCE_NP_ENTITLEMENT_ACCESS_ERROR_NO_ENTITLEMENT for a dlc i own
	// tried zero for the first two parameters, didnt work

	// returns SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER if either of the last two parameters are null

	Log_if_enabled("[dlcldr] sceNpEntitlementAccessGetAddcontEntitlementInfoIndividual called");

	return SCE_NP_ENTITLEMENT_ACCESS_ERROR_NO_ENTITLEMENT;
}

int32_t sceNpEntitlementAccessGetAddcontEntitlementInfoList(
	SceNpServiceLabel serviceLabel,
	SceNpEntitlementAccessAddcontEntitlementInfo *list,
	uint32_t listNum,
	uint32_t *hitNum)
{
	// real function returns SCE_OK even if list is null
	// returns SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER if serviceLabel is unknown

	Logf_if_enabled("[dlcldr] sceNpEntitlementAccessGetAddcontEntitlementInfoList called, listNum: %d", listNum);

	if (listNum == 0 || list == NULL)
	{
		if (hitNum == NULL)
		{
			Log_if_enabled("[dlcldr] sceNpEntitlementAccessGetAddcontEntitlementInfoList: list is null or listNum is 0, hitNum is null");
			return SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER;
		}
		*hitNum = addcont_count;
		Logf_if_enabled("[dlcldr] sceNpEntitlementAccessGetAddcontEntitlementInfoList: list is null or listNum is 0, hitNum set to %d", addcont_count);
		return SCE_OK;
	}

	int dlcsToList = addcont_count < listNum ? addcont_count : listNum;

	for (int i = 0; i < dlcsToList; i++)
	{
		strncpy(list[i].entitlementLabel.data, addcontInfo[i].entitlementLabel, SCE_NP_UNIFIED_ENTITLEMENT_LABEL_SIZE);
		list[i].downloadStatus = addcontInfo[i].status;
		list[i].packageType = addcontInfo[i].status == 4 ? SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSAC : SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSAL;
	}

	if (hitNum != NULL)
	{
		*hitNum = dlcsToList;
	}

	Logf_if_enabled("[dlcldr] sceNpEntitlementAccessGetAddcontEntitlementInfoList: returning %d dlcs", dlcsToList);
	return SCE_OK;
}

int32_t sceNpEntitlementAccessGetEntitlementKey(
	SceNpServiceLabel serviceLabel,
	const SceNpUnifiedEntitlementLabel *entitlementLabel,
	SceNpEntitlementAccessEntitlementKey *key)
{
	// returns SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER if key or entitlementLabel is null
	// returns SCE_NP_ENTITLEMENT_ACCESS_ERROR_NO_ENTITLEMENT if entitlementLabel is unknown
	
	if (key == NULL || entitlementLabel == NULL)
	{
		Log_if_enabled("[dlcldr] sceNpEntitlementAccessGetEntitlementKey: key or entitlementLabel is null, returning SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER");
		return SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER;
	}

	for (int i = 0; i < addcont_count; i++)
	{
		if (strncmp(entitlementLabel->data, addcontInfo[i].entitlementLabel, SCE_NP_UNIFIED_ENTITLEMENT_LABEL_SIZE-1))
		{ continue; }
		
		memcpy(key->data, addcontInfo[i].key, SCE_APP_CONTENT_ENTITLEMENT_KEY_SIZE);
		Logf_if_enabled("[dlcldr] sceNpEntitlementAccessGetEntitlementKey found key for %s", entitlementLabel->data);
		return SCE_OK;
	}

	Logf_if_enabled("[dlcldr] sceNpEntitlementAccessGetEntitlementKey did not find key for %s, returning SCE_NP_ENTITLEMENT_ACCESS_ERROR_NO_ENTITLEMENT", entitlementLabel->data);
	return SCE_NP_ENTITLEMENT_ACCESS_ERROR_NO_ENTITLEMENT;
}

// if its not part of ps5 4.03 its also not part of ps4 9.00
// so this could be ignored
int32_t sceNpEntitlementAccessGetGameTrialsFlag()
{
	// this isn't even part of the lib on 4.03 so i have no info
	// i got PRX_NOT_RESOLVED_FUNCTION

	Log_if_enabled("[dlcldr] sceNpEntitlementAccessGetGameTrialsFlag called");
	return SCE_OK;
}

int32_t sceNpEntitlementAccessGetSkuFlag(
	SceNpEntitlementAccessSkuFlag *skuFlag)
{
	if (skuFlag == NULL)
	{
		Log_if_enabled("[dlcldr] sceNpEntitlementAccessGetSkuFlag: skuFlag is null");
		return SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER;
	}
	
	*skuFlag = SCE_NP_ENTITLEMENT_ACCESS_SKU_FLAG_FULL;

	Logf_if_enabled("[dlcldr] sceNpEntitlementAccessGetSkuFlag: returning SCE_NP_ENTITLEMENT_ACCESS_SKU_FLAG_FULL");
	return SCE_OK;
}

int32_t sceNpEntitlementAccessInitialize(
	const SceNpEntitlementAccessInitParam *initParam,
	SceNpEntitlementAccessBootParam *bootParam)
{
	Log_if_enabled("[dlcldr] sceNpEntitlementAccessInitialize called");
	return SCE_OK;
}

int32_t sceNpEntitlementAccessRequestConsumableEntitlementInfo(
	SceUserServiceUserId userId,
	SceNpServiceLabel serviceLabel,
	const SceNpUnifiedEntitlementLabel *entitlementLabel,
	int64_t *requestId)
{
	// parameters assumed.

	// ida:
	// __int64 __fastcall sceNpEntitlementAccessRequestConsumableEntitlementInfo(unsigned int a1, unsigned int a2, __int64 a3, __int64 a4)

	if (requestId == NULL)
	{
		Log_if_enabled("[dlcldr] sceNpEntitlementAccessRequestConsumableEntitlementInfo: requestId is null");
		return SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER;
	}

	*requestId = 150; // dummy
	Log_if_enabled("[dlcldr] sceNpEntitlementAccessRequestConsumableEntitlementInfo: returning dummy requestId");
	return SCE_OK;
}

int32_t sceNpEntitlementAccessPollConsumableEntitlementInfo(
	int64_t requestId,
	int32_t *pResult,
	int32_t *useLimit)
{
	// parameters assumed.
	
	// ida:
	// __int64 __fastcall sceNpEntitlementAccessPollConsumableEntitlementInfo(__int64 a1, __int64 a2, __int64 a3)

	if (pResult == NULL || requestId == 0 || useLimit == NULL)
	{
		Log_if_enabled("[dlcldr] sceNpEntitlementAccessPollConsumableEntitlementInfo: pResult, requestId or useLimit is null, returning SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER");
		return SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER;
	}

	*pResult = -1;
	*useLimit = -1;

	Log_if_enabled("[dlcldr] sceNpEntitlementAccessPollConsumableEntitlementInfo: returning -1 pResult, and SCE_NP_ENTITLEMENT_ACCESS_POLL_RET_FINISHED");
	return SCE_NP_ENTITLEMENT_ACCESS_POLL_RET_FINISHED;
}

int32_t sceNpEntitlementAccessRequestConsumeEntitlement(
	SceUserServiceUserId userId,
	SceNpServiceLabel serviceLabel,
	const SceNpServiceEntitlementLabel *entitlementLabel,
	const SceNpEntitlementAccessTransactionId *transactionId,
	int32_t useCount,
	int64_t *requestId
)
{
	// parameters assumed.

	// ida:
	// __int64 __fastcall sceNpEntitlementAccessRequestConsumeEntitlement(int a1, int a2, int a3, int a4, int a5, __int64 a6)

	if (requestId == NULL)
	{
		Log_if_enabled("[dlcldr] sceNpEntitlementAccessRequestConsumeEntitlement: requestId is null");
		return SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER;
	}

	*requestId = 150; // dummy

	Log_if_enabled("[dlcldr] sceNpEntitlementAccessRequestConsumeEntitlement: returning dummy requestId");
	return SCE_OK;
}

int32_t sceNpEntitlementAccessRequestConsumeUnifiedEntitlement(
	SceUserServiceUserId userId,
	SceNpServiceLabel serviceLabel,
	const SceNpUnifiedEntitlementLabel *entitlementLabel,
	const SceNpEntitlementAccessTransactionId *transactionId,
	int32_t useCount,
	int64_t *requestId)
{
	// returns ok even offline

	if (requestId == NULL)
	{
		Log_if_enabled("[dlcldr] sceNpEntitlementAccessRequestConsumeUnifiedEntitlement: requestId is null");
		return SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER;
	}

	*requestId = 150; // dummy

	Log_if_enabled("[dlcldr] sceNpEntitlementAccessRequestConsumeUnifiedEntitlement: returning dummy requestId");
	return SCE_OK;
}

int32_t sceNpEntitlementAccessPollConsumeEntitlement(
	int64_t requestId,
	int32_t *pResult,
	int32_t *useLimit)
{
	// returns SCE_NP_ENTITLEMENT_ACCESS_ERROR_TITLE_TOKEN no matter what i did
	// this is not for proper dlc, its for consumables or subscriptions and we dont care about that

	*pResult = SCE_NP_ENTITLEMENT_ACCESS_ERROR_TITLE_TOKEN;
	Log_if_enabled("[dlcldr] sceNpEntitlementAccessPollConsumeEntitlement: returning pResult SCE_NP_ENTITLEMENT_ACCESS_ERROR_TITLE_TOKEN, and SCE_NP_ENTITLEMENT_ACCESS_POLL_RET_FINISHED");
	return SCE_NP_ENTITLEMENT_ACCESS_POLL_RET_FINISHED;
}

int32_t sceNpEntitlementAccessRequestServiceEntitlementInfo(
	SceUserServiceUserId userId,
	SceNpServiceLabel serviceLabel,
	const SceNpServiceEntitlementLabel *entitlementLabel,
	int64_t *requestId)
{
	if (requestId == NULL)
	{
		Log_if_enabled("[dlcldr] sceNpEntitlementAccessRequestServiceEntitlementInfo: requestId is null");
		return SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER;
	}

	*requestId = 150; // dummy

	Log_if_enabled("[dlcldr] sceNpEntitlementAccessRequestServiceEntitlementInfo: returning dummy requestId");
	return SCE_OK;
}

int32_t sceNpEntitlementAccessPollServiceEntitlementInfo(
	int64_t requestId,
	int32_t *pResult,
	SceNpEntitlementAccessServiceEntitlementInfo *info)
{
	*pResult = SCE_NP_ENTITLEMENT_ACCESS_ERROR_TITLE_TOKEN;
	Log_if_enabled("[dlcldr] sceNpEntitlementAccessPollServiceEntitlementInfo: returning pResult SCE_NP_ENTITLEMENT_ACCESS_ERROR_TITLE_TOKEN, and SCE_NP_ENTITLEMENT_ACCESS_POLL_RET_FINISHED");
	return SCE_NP_ENTITLEMENT_ACCESS_POLL_RET_FINISHED;
}

int32_t sceNpEntitlementAccessRequestServiceEntitlementInfoList(
	SceUserServiceUserId userId,
	SceNpServiceLabel serviceLabel,
	const SceNpServiceEntitlementLabel *list,
	uint32_t listNum,
	const SceNpEntitlementAccessRequestEntitlementInfoListParam *param,
	int64_t *requestId)
{
	if (param->packageType != SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_NONE)
	{
		Log_if_enabled("[dlcldr] sceNpEntitlementAccessRequestServiceEntitlementInfoList: packageType is not SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_NONE, returning SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER");
		return SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER;
	}

	if (requestId == NULL)
	{
		Log_if_enabled("[dlcldr] sceNpEntitlementAccessRequestServiceEntitlementInfoList: requestId is null");
		return SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER;
	}

	*requestId = 150; // dummy

	Log_if_enabled("[dlcldr] sceNpEntitlementAccessRequestServiceEntitlementInfoList: returning dummy requestId");
	return SCE_OK;
}

int32_t sceNpEntitlementAccessPollServiceEntitlementInfoList(
	int64_t requestId,
	int32_t *pResult,
	SceNpEntitlementAccessServiceEntitlementInfo *list,
	uint32_t listNum,
	uint32_t *hitNum,
	int32_t *nextOffset,
	int32_t *previousOffset)
{
	*pResult = SCE_NP_ENTITLEMENT_ACCESS_ERROR_TITLE_TOKEN;
	Log_if_enabled("[dlcldr] sceNpEntitlementAccessPollServiceEntitlementInfoList: returning pResult SCE_NP_ENTITLEMENT_ACCESS_ERROR_TITLE_TOKEN, and SCE_NP_ENTITLEMENT_ACCESS_POLL_RET_FINISHED");
	return SCE_NP_ENTITLEMENT_ACCESS_POLL_RET_FINISHED;
}

int32_t sceNpEntitlementAccessRequestUnifiedEntitlementInfo(
	SceUserServiceUserId userId,
	SceNpServiceLabel serviceLabel,
	const SceNpUnifiedEntitlementLabel *entitlementLabel,
	int64_t *requestId)
{
	if (requestId == NULL)
	{
		Log_if_enabled("[dlcldr] sceNpEntitlementAccessRequestUnifiedEntitlementInfo: requestId is null");
		return SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER;
	}

	*requestId = 150; // dummy

	Log_if_enabled("[dlcldr] sceNpEntitlementAccessRequestUnifiedEntitlementInfo: returning dummy requestId");
	return SCE_OK;
}

int32_t sceNpEntitlementAccessPollUnifiedEntitlementInfo(
	int64_t requestId,
	int32_t *pResult,
	SceNpEntitlementAccessUnifiedEntitlementInfo *info)
{
	// real function doesnt touch info
	*pResult = SCE_NP_ENTITLEMENT_ACCESS_ERROR_TITLE_TOKEN;
	Log_if_enabled("[dlcldr] sceNpEntitlementAccessPollUnifiedEntitlementInfo: returning pResult SCE_NP_ENTITLEMENT_ACCESS_ERROR_TITLE_TOKEN, and SCE_NP_ENTITLEMENT_ACCESS_POLL_RET_FINISHED");
	return SCE_NP_ENTITLEMENT_ACCESS_POLL_RET_FINISHED;
}

int32_t sceNpEntitlementAccessRequestUnifiedEntitlementInfoList(
	SceUserServiceUserId userId,
	SceNpServiceLabel serviceLabel,
	const SceNpUnifiedEntitlementLabel *list,
	uint32_t listNum,
	const SceNpEntitlementAccessRequestEntitlementInfoListParam *param,
	int64_t *requestId)
{
	// findings on console with ps servers blocked, but it would probably be the same if they weren't
	// since its on an old firmware

	// param.packageType = SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_NONE 	-> SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER
	// param.packageType = SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSGD -> SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER
	// param.packageType = SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSAC -> SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER
	// param.packageType = SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSAL -> SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER
	// param.packageType = SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSCONS -> SCE_OK
	// param.packageType = SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSVC -> SCE_OK
	// param.packageType = SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSSUBS -> SCE_OK

	// this means this function is only for online stuff, we only care about psac and psal

	if (param->packageType == SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_NONE ||
		param->packageType == SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSGD ||
		param->packageType == SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSAC ||
		param->packageType == SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSAL)
	{
		Log_if_enabled("[dlcldr] sceNpEntitlementAccessRequestUnifiedEntitlementInfoList: packageType is not in whitelist, returning SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER");
		return SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER;
	}

	Log_if_enabled("[dlcldr] sceNpEntitlementAccessRequestUnifiedEntitlementInfoList returned SCE_OK");
	return SCE_OK;
}

int32_t sceNpEntitlementAccessPollUnifiedEntitlementInfoList(
	int64_t requestId,
	int32_t *pResult,
	SceNpEntitlementAccessUnifiedEntitlementInfo *list,
	uint32_t listNum,
	uint32_t *hitNum,
	int32_t *nextOffset,
	int32_t *previousOffset)
{
	// real function doesnt touch hitNum
	*pResult = SCE_NP_ENTITLEMENT_ACCESS_ERROR_TITLE_TOKEN;
	Log_if_enabled("[dlcldr] sceNpEntitlementAccessPollUnifiedEntitlementInfoList: returning pResult SCE_NP_ENTITLEMENT_ACCESS_ERROR_TITLE_TOKEN, and SCE_NP_ENTITLEMENT_ACCESS_POLL_RET_FINISHED");
	return SCE_NP_ENTITLEMENT_ACCESS_POLL_RET_FINISHED;
}

int32_t sceNpEntitlementAccessRequestConsumeServiceEntitlement(
	SceUserServiceUserId userId,
	SceNpServiceLabel serviceLabel,
	const SceNpServiceEntitlementLabel *entitlementLabel,
	const SceNpEntitlementAccessTransactionId *transactionId,
	int32_t useCount,
	int64_t *requestId)
{
	if (requestId == NULL)
	{
		return SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER;
	}

	*requestId = 150; // dummy

	Log_if_enabled("[dlcldr] sceNpEntitlementAccessRequestConsumeServiceEntitlement: returning dummy requestId");
	return SCE_OK;
}