#include "common.h"

#define bool int
#define false 0
#define true 1

#define SCE_NP_ENTITLEMENT_ACCESS_ERROR_NO_ENTITLEMENT -2122514425	// 0x817D0007

#define SCE_NP_ENTITLEMENT_ACCESS_SKU_FLAG_TRIAL					(1)		// Trial
#define SCE_NP_ENTITLEMENT_ACCESS_SKU_FLAG_FULL						(3)		// Full

#define SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_NONE						(0)	
#define SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PS4GD					(1)	
#define SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PS4AC					(2)	
#define SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PS4AL					(3)	
#define SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSCONS					(4)	
#define SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSVC						(5)	
#define SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSSUBS					(6)	

#define SCE_NP_ENTITLEMENT_ACCESS_DOWNLOAD_STATUS_NO_EXTRA_DATA			(0)
#define SCE_NP_ENTITLEMENT_ACCESS_DOWNLOAD_STATUS_NO_IN_QUEUE			(1)
#define SCE_NP_ENTITLEMENT_ACCESS_DOWNLOAD_STATUS_DOWNLOADING			(2)
#define SCE_NP_ENTITLEMENT_ACCESS_DOWNLOAD_STATUS_DOWNLOAD_SUSPENDED	(3)
#define SCE_NP_ENTITLEMENT_ACCESS_DOWNLOAD_STATUS_INSTALLED				(4)
																				
#define SCE_NP_ENTITLEMENT_ACCESS_ENTITLEMENT_TYPE_NONE						(0)
#define SCE_NP_ENTITLEMENT_ACCESS_ENTITLEMENT_TYPE_SERVICE					(1)
#define SCE_NP_ENTITLEMENT_ACCESS_ENTITLEMENT_TYPE_UNIFIED					(2)


typedef uint32_t SceNpEntitlementAccessPackageType;
typedef uint32_t SceNpEntitlementAccessDownloadStatus;

typedef struct SceNpEntitlementAccessAddcontEntitlementInfo
{
	SceNpUnifiedEntitlementLabel entitlementLabel;
	SceNpEntitlementAccessPackageType packageType;
	SceNpEntitlementAccessDownloadStatus downloadStatus;
} SceNpEntitlementAccessAddcontEntitlementInfo;


#define SCE_NP_ENTITLEMENT_ACCESS_ENTITLEMENT_KEY_SIZE (16)
typedef struct SceNpEntitlementAccessEntitlementKey
{
	char data[SCE_NP_ENTITLEMENT_ACCESS_ENTITLEMENT_KEY_SIZE];
} SceNpEntitlementAccessEntitlementKey;

typedef struct SceNpEntitlementAccessInitParam {
	char	reserved[32];
} SceNpEntitlementAccessInitParam;

typedef struct SceNpEntitlementAccessBootParam {
	char	reserved[32];
} SceNpEntitlementAccessBootParam;

typedef uint32_t SceNpEntitlementAccessSkuFlag;

#define SCE_NP_ENTITLEMENT_ACCESS_TRANSACTION_ID_MAX_SIZE	(65)

typedef struct SceNpEntitlementAccessTransactionId {
	char	transactionId[SCE_NP_ENTITLEMENT_ACCESS_TRANSACTION_ID_MAX_SIZE];
	char	padding[7];														
} SceNpEntitlementAccessTransactionId;

typedef int SceUserServiceUserId;

typedef uint32_t SceNpEntitlementAccessEntitlementType;
typedef uint32_t SceNpEntitlementAccessSortType;
typedef uint32_t SceNpEntitlementAccessDirectionType;
typedef struct SceNpEntitlementAccessRequestEntitlementInfoListParam {
	size_t size;												
	SceNpEntitlementAccessEntitlementType entitlementType;	
	int32_t offset;											
	int32_t limit;											
	SceNpEntitlementAccessSortType sort;					
	SceNpEntitlementAccessDirectionType direction;			
	SceNpEntitlementAccessPackageType packageType;			
} SceNpEntitlementAccessRequestEntitlementInfoListParam;


#define SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER -2122514430	// 0x817D0002

#define SCE_NP_ENTITLEMENT_ACCESS_ERROR_TITLE_TOKEN -2122514407	// 0x817D0019

typedef struct SceRtcTick {
	uint64_t tick;
} SceRtcTick;

typedef struct SceNpEntitlementAccessUnifiedEntitlementInfo {
	SceNpUnifiedEntitlementLabel entitlementLabel;			
	SceRtcTick activeDate;									
	SceRtcTick inactiveDate;								
	SceNpEntitlementAccessEntitlementType entitlementType;	
	int32_t useCount;										
	int32_t useLimit;										
	SceNpEntitlementAccessPackageType	packageType;		
	bool activeFlag;										
	int8_t reserved[3];										
} SceNpEntitlementAccessUnifiedEntitlementInfo;

#define SCE_NP_SERVICE_ENTITLEMENT_LABEL_SIZE	(7)
typedef struct SceNpServiceEntitlementLabel {
	char data[SCE_NP_SERVICE_ENTITLEMENT_LABEL_SIZE];
	char padding[13];
} SceNpServiceEntitlementLabel;

typedef struct SceNpEntitlementAccessServiceEntitlementInfo {
	SceNpServiceEntitlementLabel entitlementLabel;			
	SceRtcTick activeDate;									
	SceRtcTick inactiveDate;								
	SceNpEntitlementAccessEntitlementType entitlementType;	
	int32_t useCount;										
	int32_t useLimit;										
	uint32_t reserved1;										
	bool activeFlag;										
	bool isConsumable;										
	int8_t reserved2[2];									
} SceNpEntitlementAccessServiceEntitlementInfo;

#define SCE_NP_ENTITLEMENT_ACCESS_POLL_RET_FINISHED								(0)
#define SCE_NP_ENTITLEMENT_ACCESS_POLL_ASYNC_RET_RUNNING						(1)