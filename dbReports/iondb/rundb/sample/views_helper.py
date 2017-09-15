# Copyright (C) 2013 Ion Torrent Systems, Inc. All Rights Reserved

from django.template import RequestContext
from django.shortcuts import get_object_or_404

import datetime
from django.utils import timezone
import logging

from traceback import format_exc
import json
import simplejson

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from iondb.rundb import models

from iondb.rundb.models import Sample, SampleSet, SampleSetItem, SampleAttribute, SampleGroupType_CV,  \
    SampleAttributeDataType, SampleAttributeValue, SamplePrepData

from django.contrib.auth.models import User

import sample_validator

logger = logging.getLogger(__name__)


def validate_for_existing_samples(request, sampleSet_ids):
    if 'input_samples' in request.session:
        if 'pending_sampleSetItem_list' in request.session['input_samples']:
            pending_sampleSetItem_list = request.session['input_samples']['pending_sampleSetItem_list']
        else:
            pending_sampleSetItem_list = []
    else:
        pending_sampleSetItem_list = []

    for sampleset_id in sampleSet_ids:
        sampleset = models.SampleSet.objects.get(pk=sampleset_id)
        samplesetitems = sampleset.samples.all()

        if samplesetitems:
            for item in samplesetitems:
                # first validate that all barcode kits are the same for all samples
                # logger.debug("views_heoper.validate_for_existing_samples() item.dnabarcode=%s" %(item.dnabarcode))

                if item.dnabarcode:
                    dnabarcode = item.dnabarcode
                    barcodeKit = dnabarcode.name
                    barcode = dnabarcode.id_str
                else:
                    barcodeKit = None
                    barcode = None

                pcrPlateRow = item.pcrPlateRow

                for item1 in pending_sampleSetItem_list:
                    barcodeKit1 = item1.get('barcodeKit')
                    barcode1 = item1.get('barcode')
                    if barcodeKit and barcodeKit1 and barcodeKit != barcodeKit1:
                        # logger.debug("views_helper... barcodeKit=%s; barcodeKit1=%s" %(barcodeKit, barcodeKit1))
                        return False, "Error, Only one barcode kit can be used for a sample set. %s is the barcode kit for this sample set" % (barcodeKit)

                    # next validate that all barcodes are unique per each sample
                    if barcode and barcode1 and barcode == barcode1:
                        return False, "Error, A barcode can be assigned to only one sample in the sample set. %s has been assigned to another sample" % (barcode)

                    pcrPlateRow1 = item1.get("pcrPlateRow")
                    if (pcrPlateRow and pcrPlateRow1 and pcrPlateRow.lower() == pcrPlateRow1.lower()):
                        return False, "Error, A PCR plate position can only have one sample in it. Position %s has already been occupied by another sample" % (pcrPlateRow)

                    if (not pcrPlateRow1 and "amps_on_chef" in sampleset.libraryPrepType.lower()):
                        return False, "Error, A PCR plate position must be specified for AmpliSeq on Chef sample %s" % (item1.get("displayedName"))

        elif pending_sampleSetItem_list:
            return validate_pending_sampleSetItem_for_sampleSets(pending_sampleSetItem_list, sampleSet_ids)

    return True, None


def validate_pending_sampleSetItem_for_sampleSets(pending_sampleSetItem_list, sampleSet_ids):
    """
    Validates the pending sample set items based on the characteristics of the sample sets.
    Returns a boolean to indicate if there is any error and an error message if any
    """

    isValid = True
    errorMessage = None

    for sampleset_id in sampleSet_ids:
        sampleset = models.SampleSet.objects.get(pk=sampleset_id)
        for pending_item in pending_sampleSetItem_list:
            isVald, errorMessage = sample_validator.validate_barcoding_samplesetitems(pending_sampleSetItem_list, pending_item.get('barcodeKit', None), \
                                                                                      pending_item.get('barcode', None), None, pending_id=pending_item.get('pending_id', ""))
            if not isValid:
                return isValid, errorMessage

            isValid, errorMessage = sample_validator.validate_pcrPlate_position_samplesetitems(pending_sampleSetItem_list, pending_item.get('pcrPlateRow', ""), \
                                                                                               None, pending_item.get('pending_id', ""), sampleset)
            if not isValid:
                return isValid, errorMessage

    return isValid, errorMessage


def _get_or_create_sampleSets(request, user):
    queryDict = request.POST
    logger.info("views._get_or_create_sampleSets POST queryDict=%s" % (queryDict))

    sampleSet_ids = []

    new_sampleSetName = queryDict.get("new_sampleSetName", "").strip()
    new_sampleSetDesc = queryDict.get("new_sampleSetDescription", "").strip()
    new_sampleSet_groupType_id = queryDict.get("new_sampleSet_groupType", None)
    new_sampleSet_libraryPrepType = queryDict.get("new_sampleSet_libraryPrepType", "").strip()
    new_sampleSet_libraryPrepKitName = queryDict.get("new_sampleSet_libraryPrepKit", "").strip()

    new_sampleSet_pcrPlateSerialNum = queryDict.get("new_sampleSet_pcrPlateSerialNum", "").strip()

    selected_sampleSet_ids = queryDict.getlist("sampleset", [])

    # logger.debug("views_helper._get_or_create_sampleSets selected_sampleSet_ids=%s" %(selected_sampleSet_ids))

    if selected_sampleSet_ids:
        selected_sampleSet_ids = [ssi.encode('utf8') for ssi in selected_sampleSet_ids]

    if (selected_sampleSet_ids):
        sampleSet_ids.extend(selected_sampleSet_ids)

    # logger.debug("views_helper._get_or_create_sampleSets sampleSet_ids=%s" %(sampleSet_ids))

    # nullify group type if user does not specify a group type
    if new_sampleSet_groupType_id == '0' or new_sampleSet_groupType_id == 0:
        new_sampleSet_groupType_id = None

    # if new_sampleSetName is missing, the rest of the input will be ignored
    if new_sampleSetName:
        isValid, errorMessage = sample_validator.validate_sampleSet_values(new_sampleSetName, new_sampleSetDesc, new_sampleSet_pcrPlateSerialNum, True)

        if errorMessage:
            return isValid, errorMessage, sampleSet_ids

        currentDateTime = timezone.now()  ##datetime.datetime.now()

        sampleSetStatus = "created"
        if new_sampleSet_libraryPrepType and "chef" in new_sampleSet_libraryPrepType.lower():
            libraryPrepInstrument = "chef"
            sampleSetStatus = "libPrep_pending"
        else:
            libraryPrepInstrument = ""

        sampleSet_kwargs = {
            'description': new_sampleSetDesc,
            'pcrPlateSerialNum': new_sampleSet_pcrPlateSerialNum,
            'libraryPrepKitName': new_sampleSet_libraryPrepKitName,
            'status': sampleSetStatus,
            'creationDate': currentDateTime,
            'lastModifiedUser': user,
            'lastModifiedDate': currentDateTime
            }

        sampleSet, isCreated = SampleSet.objects.get_or_create(
            displayedName=new_sampleSetName.strip(),
            SampleGroupType_CV_id=new_sampleSet_groupType_id,
            libraryPrepType=new_sampleSet_libraryPrepType,
            libraryPrepInstrument=libraryPrepInstrument,
            creator=user,
            defaults=sampleSet_kwargs)

        if isCreated:
            if sampleSet.libraryPrepInstrument == "chef":
                libraryPrepInstrumentData_obj = models.SamplePrepData.objects.create(samplePrepDataType="lib_prep")
                sampleSet.libraryPrepInstrumentData = libraryPrepInstrumentData_obj
                logger.debug("views_helper - sampleSet.id=%d; isCreated=%s; GOING TO ADD libraryPrepInstrumentData_obj.id=%d" % (sampleSet.id, str(isCreated), libraryPrepInstrumentData_obj.id))
                sampleSet.save()
        else:
            if sampleSet.libraryPrepInstrument == "":
                if sampleSet.libraryPrepInstrumentData:
                    logger.debug("views_helper - sampleSet.id=%d; isCreated=%s; GOIGN TO DELETE libraryPrepInstrumentData_obj.id=%d" % (sampleSet.id, str(isCreated), sampleSet.libraryPrepInstrumentData.id))
                    sampleSet.libraryPrepInstrumentData.delete()
                    # sampleSet.save()

        # logger.debug("views_helper._get_or_create_sampleSets sampleSetName=%s isCreated=%s" %(new_sampleSetName, str(isCreated)))
        sampleSet_ids.append(sampleSet.id)

    logger.debug("views_helper._get_or_create_sampleSets EXIT sampleSet_ids=%s" % (sampleSet_ids))

    return True, None, sampleSet_ids


def _create_or_update_sample_for_sampleSetItem(request, user):
    queryDict = request.POST

    sampleSetItem_id = queryDict.get("id", None)
    sampleDisplayedName = queryDict.get("sampleName", "").strip()
    sampleExternalId = queryDict.get("sampleExternalId", "").strip()
    sampleDesc = queryDict.get("sampleDescription", "").strip()
    # 20130930-TODO
    # barcode info
    barcodeKit = queryDict.get("barcodeKit", "").strip()
    barcode = queryDict.get("barcode", "").strip()

    return _create_or_update_sample_for_sampleSetItem_with_id_values(request, user, sampleSetItem_id, sampleDisplayedName, sampleExternalId, sampleDesc, barcodeKit, barcode)


def _create_or_update_sample_for_sampleSetItem_with_id_values(request, user, sampleSetItem_id, sampleDisplayedName, sampleExternalId, sampleDesc, barcodeKit, barcode):
    currentDateTime = timezone.now()  ##datetime.datetime.now()

    orig_sampleSetItem = get_object_or_404(SampleSetItem, pk=sampleSetItem_id)
    orig_sample = orig_sampleSetItem.sample

    if (orig_sample.displayedName == sampleDisplayedName and
            orig_sample.externalId == sampleExternalId.strip()):
        # logger.debug("views_helper - _create_or_update_sample_for_sampleSetItem_with_id_values - #1 can REUSE SAMPLE for sure!! sampleSetItem.id=%d; sample.id=%d" %(orig_sampleSetItem.id, orig_sample.id))

        new_sample = orig_sample

        if (new_sample.description != sampleDesc):
            new_sample.description = sampleDesc
            new_sample.date = currentDateTime

            # logger.debug("views_helper - _create_or_update_sample_for_sampleSetItem_with_id_values - #2 REUSE SAMPLE + UPDATE DESC sampleSetItem.id=%d; sample.id=%d" %(orig_sampleSetItem.id, new_sample.id))
            new_sample.save()
    else:
        # link the renamed sample to an existing sample if one is found. Otherwise, rename the sample only if the sample has not yet been planned.
        existingSamples = Sample.objects.filter(displayedName=sampleDisplayedName, externalId=sampleExternalId)

        canSampleBecomeOrphan = (orig_sample.sampleSets.count() < 2) and orig_sample.experiments.count() == 0
        logger.info("views_helper - _create_or_update_sample_for_sampleSetItem_with_id_values - #3 can sample becomes ORPHAN? orig_sample.id=%d; orig_sample.name=%s; canSampleBecomeOrphan=%s" % (orig_sample.id, orig_sample.displayedName, str(canSampleBecomeOrphan)))

        if existingSamples.count() > 0:
            orig_sample_id = orig_sample.id

            # by sample uniqueness rule, there should only be 1 existing sample max
            existingSample = existingSamples[0]
            existingSample.description = sampleDesc
            orig_sampleSetItem.sample = existingSample
            orig_sampleSetItem.lastModifiedUser = user
            orig_sampleSetItem.lastModifiedDate = currentDateTime

            if barcode:
                orig_sampleSetItem.barcode = barcode

            orig_sampleSetItem.save()

            new_sample = existingSample

            logger.debug("views_helper - _create_or_update_sample_for_sampleSetItem_with_id_values - #4 SWITCH TO EXISTING SAMPLE sampleSetItem.id=%d; existingSample.id=%d" % (orig_sampleSetItem.id, existingSample.id))

            # cleanup if the replaced sample is not being used anywhere
            if canSampleBecomeOrphan:
                logger.debug("views_helper - _create_or_update_sample_for_sampleSetItem_with_id_values - #5 AFTER SWITCH orig_sample becomes ORPHAN! orig_sample.id=%d; orig_sample.name=%s" % (orig_sample.id, orig_sample.displayedName))
                orig_sample.delete()
            else:
                logger.debug("views_helper - _create_or_update_sample_for_sampleSetItem_with_id_values - #6 AFTER SWITCH orig_sample is still NOT ORPHAN YET! orig_sample.id=%d; orig_sample.name=%s sample.sampleSets.count=%d; sample.experiments.count=%d; " % (orig_sample.id, orig_sample.displayedName, orig_sample.sampleSets.count(), orig_sample.experiments.count()))
        else:
            name = sampleDisplayedName.replace(' ', '_')

            if canSampleBecomeOrphan:
                # update existing sample record
                sample_kwargs = {
                    'name': name,
                    'displayedName': sampleDisplayedName,
                    'description': sampleDesc,
                    'externalId': sampleExternalId,
                    'description': sampleDesc,
                    'date': currentDateTime,
                    }
                for field, value in sample_kwargs.iteritems():
                    setattr(orig_sample, field, value)

                orig_sample.save()

                logger.debug("views_helper - _create_or_update_sample_for_sampleSetItem_with_id_values - #7 RENAME SAMPLE sampleSetItem.id=%d; sample.id=%d" % (orig_sampleSetItem.id, orig_sample.id))
                new_sample = orig_sample
            else:
                # create a new sample record
                sample_kwargs = {
                    'displayedName': sampleDisplayedName,
                    'description': sampleDesc,
                    'status': "created",
                    'date': currentDateTime,
                }

                sample = Sample.objects.get_or_create(name=name, externalId=sampleExternalId, defaults=sample_kwargs)[0]

                orig_sampleSetItem.sample = sample

                if barcode:
                    orig_sampleSetItem.barcode = barcode

                orig_sampleSetItem.save()

                logger.debug("views_helper - _create_or_update_sample_for_sampleSetItem_with_id_values - #8 CREATE NEW SAMPLE sampleSetItem.id=%d; sample.id=%d" % (orig_sampleSetItem.id, sample.id))
                new_sample = sample

    return new_sample


def _create_or_update_sample_for_sampleSetItem_with_values(request, user, sampleDisplayedName, sampleExternalId, sampleDesc, barcodeKit, barcode):
    currentDateTime = timezone.now()  ##datetime.datetime.now()

    sample = None
    existingSamples = Sample.objects.filter(displayedName=sampleDisplayedName, externalId=sampleExternalId)

    if existingSamples.count() > 0:
        existingSample = existingSamples[0]
        existingSample.description = sampleDesc
        existingSample.date = currentDateTime

        logger.debug("views_helper._create_or_update_sample_for_sampleSetItem_with_values() #9 updating sample.id=%d; name=%s" % (existingSample.id, existingSample.displayedName))

        existingSample.save()
        sample = existingSample
    else:
        # create a new sample record
        name = sampleDisplayedName.replace(' ', '_')

        sample_kwargs = {
            'displayedName': sampleDisplayedName,
            'description': sampleDesc,
            'status': "created",
            'date': currentDateTime,
        }

        sample = Sample.objects.get_or_create(name=name, externalId=sampleExternalId, defaults=sample_kwargs)[0]

        logger.debug("views_helper._create_or_update_sample_for_sampleSetItem_with_values() #10 create new sample.id=%d; name=%s" % (sample.id, sample.displayedName))

    return sample


def _update_input_samples_session_context(request, pending_sampleSetItem, isNew=True):
    logger.debug("views_helper._update_input_samples_session_context pending_sampleSetItem=%s" % (pending_sampleSetItem))

    _create_pending_session_if_needed(request)

    if isNew:
        request.session["input_samples"]["pending_sampleSetItem_list"].insert(0, pending_sampleSetItem)
    else:
        pendingList = request.session["input_samples"]["pending_sampleSetItem_list"]
        hasUpdated = False

        for index, item in enumerate(pendingList):
            # logger.debug("views_helper._update_input_samples_session_context - item[pending_id]=%s; updated item.pending_id=" %(str(item['pending_id']), str(pending_sampleSetItem['pending_id'])))

            if item['pending_id'] == pending_sampleSetItem['pending_id'] and not hasUpdated:
                pendingList[index] = pending_sampleSetItem
                hasUpdated = True

        if not hasUpdated:
            request.session["input_samples"]["pending_sampleSetItem_list"].insert(0, pending_sampleSetItem)

    request.session.modified = True

    logger.debug("views_helper._update_input_samples_session_context AFTER UPDATE!! session_contents=%s" % (request.session["input_samples"]))


def _create_pending_session_if_needed(request):
    """
    return or create a session context for entering samples manually to create a sample set
    """
    if "input_samples" not in request.session:

        logger.debug("views_helper._create_pending_session_if_needed() going to CREATE new request.session")

        sampleSet_list = SampleSet.objects.all().order_by("-lastModifiedDate", "displayedName")
        sampleGroupType_list = list(SampleGroupType_CV.objects.filter(isActive=True).order_by("displayedName"))
#        custom_sample_column_list = list(SampleAttribute.objects.filter(isActive = True).values_list('displayedName', flat=True).order_by('id'))

        pending_sampleSetItem_list = []

        request.session["input_samples"] = {}
        request.session["input_samples"]['pending_sampleSetItem_list'] = pending_sampleSetItem_list

    else:
        logger.debug("views_helper._create_pending_session_if_needed() ALREADY EXIST request.session[input_samples]=%s" % (request.session["input_samples"]))


def _handle_enter_samples_manually_request(request):
    _create_pending_session_if_needed(request)

    ctxd = _create_context_from_session(request)

    return ctxd


def _create_context_from_session(request):
#    ctxd = request.session['input_samples'],

    custom_sample_column_list = list(SampleAttribute.objects.filter(isActive=True).values_list('displayedName', flat=True).order_by('id'))

    ctx = {
        'input_samples': request.session.get('input_samples', {}),
        'custom_sample_column_list': simplejson.dumps(custom_sample_column_list),
    }

    context = RequestContext(request, ctx)

    return context


def _create_pending_sampleSetItem_dict(request, userName, creationTimeStamp):
    currentDateTime = timezone.now()  ##datetime.datetime.now()

    queryDict = request.POST

    sampleSetItem_id = queryDict.get("id", None)
    sampleDisplayedName = queryDict.get("sampleName", "").strip()
    sampleExternalId = queryDict.get("sampleExternalId", "").strip()
    sampleDesc = queryDict.get("sampleDescription", "").strip()
    controlType = queryDict.get("controlType", "")

    barcodeKit = queryDict.get("barcodeKit", None)
    barcode = queryDict.get("barcode", None)
    gender = queryDict.get("gender", "")
    relationshipRole = queryDict.get("relationshipRole", "")
    relationshipGroup = queryDict.get("relationshipGroup", None)

    cancerType = queryDict.get("cancerType", "")
    cellularityPct = queryDict.get("cellularityPct", None)

    nucleotideType = queryDict.get("nucleotideType", "")
    pcrPlateRow = queryDict.get("pcrPlateRow", "").strip()

    biopsyDays = queryDict.get("biopsyDays", "0")
    cellNum = queryDict.get("cellNum", "")
    coupleId = queryDict.get("coupleId", "")
    embryoId = queryDict.get("embryoId", "")

    isValid, errorMessage, sampleAttributes_dict = _create_pending_sampleAttributes_for_sampleSetItem(request)

    if errorMessage:
        return isValid, errorMessage, sampleAttributes_dict

    # create a sample object without saving it to db
    name = sampleDisplayedName.replace(' ', '_')

    sampleSetItem_dict = {}
    sampleSetItem_dict['pending_id'] = _get_pending_sampleSetItem_id(request)
    sampleSetItem_dict['name'] = name
    sampleSetItem_dict['displayedName'] = sampleDisplayedName
    sampleSetItem_dict['externalId'] = sampleExternalId
    sampleSetItem_dict['description'] = sampleDesc
    sampleSetItem_dict['controlType'] = controlType

    sampleSetItem_dict['barcodeKit'] = barcodeKit
    sampleSetItem_dict['barcode'] = barcode
    sampleSetItem_dict['status'] = "created"

    sampleSetItem_dict['nucleotideType'] = nucleotideType
    sampleSetItem_dict['pcrPlateRow'] = pcrPlateRow
    sampleSetItem_dict['gender'] = gender
    sampleSetItem_dict['relationshipRole'] = relationshipRole
    sampleSetItem_dict['relationshipGroup'] = relationshipGroup
    sampleSetItem_dict['attribute_dict'] = sampleAttributes_dict

    sampleSetItem_dict['cancerType'] = cancerType
    sampleSetItem_dict['cellularityPct'] = cellularityPct

    sampleSetItem_dict["biopsyDays"] = biopsyDays if biopsyDays else "0"
    sampleSetItem_dict["cellNum"] = cellNum
    sampleSetItem_dict["coupleId"] = coupleId
    sampleSetItem_dict["embryoId"] = embryoId

    # logger.debug("views_helper._create_pending_sampleSetItem_dict=%s" %(sampleSetItem_dict))

    return isValid, errorMessage, sampleSetItem_dict


def _update_pending_sampleSetItem_dict(request, userName, creationTimeStamp):
    currentDateTime = timezone.now()  ##datetime.datetime.now()

    queryDict = request.POST

    sampleSetItem_id = queryDict.get("id", None)
    sampleSetItem_pendingId = queryDict.get("pending_id", None)

    # logger.debug("views_helper._update_pending_sampleSetItem_dict id=%s; pendingId=%s" %(sampleSetItem_id, sampleSetItem_pendingId))
    if sampleSetItem_pendingId is None:
        sampleSetItem_pendingId = _get_pending_sampleSetItem_id(request)
    else:
        sampleSetItem_pendingId = int(sampleSetItem_pendingId)

    sampleDisplayedName = queryDict.get("sampleName", "").strip()
    sampleExternalId = queryDict.get("sampleExternalId", "").strip()
    sampleDesc = queryDict.get("sampleDescription", "").strip()
    controlType = queryDict.get("controlType", "")

    gender = queryDict.get("gender", "")
    relationshipRole = queryDict.get("relationshipRole", "")
    relationshipGroup = queryDict.get("relationshipGroup", None)

    nucleotideType = queryDict.get("nucleotideType", "")
    pcrPlateRow = queryDict.get("pcrPlateRow", "").strip()

    cancerType = queryDict.get("cancerType", "")
    cellularityPct = queryDict.get("cellularityPct", None)

    barcodeKit = queryDict.get("barcodeKit", "")
    barcode = queryDict.get("barcode", "")

    biopsyDays = queryDict.get("biopsyDays", "0")
    cellNum = queryDict.get("cellNum", "")
    coupleId = queryDict.get("coupleId", "")
    embryoId = queryDict.get("embryoId", "")

    isValid, errorMessage, sampleAttributes_dict = _create_pending_sampleAttributes_for_sampleSetItem(request)

    if errorMessage:
        return isValid, errorMessage, sampleAttributes_dict

    # create a sample object without saving it to db
    name = sampleDisplayedName.replace(' ', '_')

    sampleSetItem_dict = {}
    sampleSetItem_dict['pending_id'] = sampleSetItem_pendingId
    sampleSetItem_dict['name'] = name
    sampleSetItem_dict['displayedName'] = sampleDisplayedName
    sampleSetItem_dict['externalId'] = sampleExternalId
    sampleSetItem_dict['description'] = sampleDesc
    sampleSetItem_dict['controlType'] = controlType
    sampleSetItem_dict['status'] = "created"

    sampleSetItem_dict['nucleotideType'] = nucleotideType
    sampleSetItem_dict['pcrPlateRow'] = pcrPlateRow
    sampleSetItem_dict['gender'] = gender
    sampleSetItem_dict['relationshipRole'] = relationshipRole
    sampleSetItem_dict['relationshipGroup'] = relationshipGroup

    sampleSetItem_dict['cancerType'] = cancerType
    sampleSetItem_dict['cellularityPct'] = cellularityPct

    sampleSetItem_dict['barcodeKit'] = barcodeKit
    sampleSetItem_dict['barcode'] = barcode
    sampleSetItem_dict['attribute_dict'] = sampleAttributes_dict

    sampleSetItem_dict["biopsyDays"] = biopsyDays if biopsyDays else "0"
    sampleSetItem_dict["cellNum"] = cellNum
    sampleSetItem_dict["coupleId"] = coupleId
    sampleSetItem_dict["embryoId"] = embryoId

    # logger.debug("views_helper._create_pending_sampleSetItem_dict=%s" %(sampleSetItem_dict))

    return isValid, errorMessage, sampleSetItem_dict


def _get_pending_sampleSetItem_id(request):
    return _get_pending_sampleSetItem_count(request) + 1


def _get_pending_sampleSetItem_count(request):
    _create_pending_session_if_needed(request)

    return len(request.session["input_samples"]["pending_sampleSetItem_list"])


def _get_pending_sampleSetItem_by_id(request, _id):

    if _id and "input_samples" in request.session:
        items = request.session["input_samples"]["pending_sampleSetItem_list"]

        for index, item in enumerate(request.session["input_samples"]["pending_sampleSetItem_list"]):
            # logger.debug("views_helper._get_pending_sampleSetItem_by_id - item[pending_id]=%s; _id=%s" %(str(item['pending_id']), str(_id)))

            if str(item['pending_id']) == str(_id):
                return item

        return None
    else:
        return None


def _create_pending_sampleAttributes_for_sampleSetItem(request):

    sampleAttribute_list = SampleAttribute.objects.filter(isActive=True).order_by('id')

    pending_attributeValue_dict = {}

    new_attributeValue_dict = {}
    for attribute in sampleAttribute_list:
        value = request.POST.get("sampleAttribute|" + str(attribute.id), None)

        if value:
            isValid, errorMessage = sample_validator.validate_sampleAttribute(attribute, value.encode('utf8'))
            if not isValid:
                return isValid, errorMessage, None
        else:
            isValid, errorMessage = sample_validator.validate_sampleAttribute_mandatory_for_no_value(attribute)
            if not isValid:
                return isValid, errorMessage, None

        new_attributeValue_dict[attribute.id] = value.encode('utf8') if value else None

    # logger.debug("views_helper._create_pending_sampleAttributes_for_sampleSetItem#1 new_attributeValue_dict=%s" %(str(new_attributeValue_dict)))

    if new_attributeValue_dict:
        for key, newValue in new_attributeValue_dict.items():
            sampleAttribute_objs = SampleAttribute.objects.filter(id=key)

            if sampleAttribute_objs.count() > 0:
                if newValue:
                    pending_attributeValue_dict[sampleAttribute_objs[0].displayedName] = newValue

    return True, None, pending_attributeValue_dict


def _create_or_update_sampleAttributes_for_sampleSetItem(request, user, sample):
    queryDict = request.POST

    sampleAttribute_list = SampleAttribute.objects.filter(isActive=True).order_by('id')

    new_attributeValue_dict = {}
    for attribute in sampleAttribute_list:
        value = request.POST.get("sampleAttribute|" + str(attribute.id), None)

        if value:
            logger.debug("views_helper._create_or_update_sampleAttributes_for_sampleSetItem() attribute=%s; value=%s" % (attribute.displayedName, value))

            isValid, errorMessage = sample_validator.validate_sampleAttribute(attribute, value.encode('utf8'))
            if not isValid:
                return isValid, errorMessage
        else:

            logger.debug("views_helper._create_or_update_sampleAttributes_for_sampleSetItem() NO VALUE attribute=%s;" % (attribute.displayedName))

            isValid, errorMessage = sample_validator.validate_sampleAttribute_mandatory_for_no_value(attribute)
            if not isValid:
                return isValid, errorMessage

        new_attributeValue_dict[attribute.id] = value.encode('utf8') if value else None

    logger.debug("views_helper._create_or_update_sampleAttributes_for_sampleSetItem #1 new_attributeValue_dict=%s" % (str(new_attributeValue_dict)))

    _create_or_update_sampleAttributes_for_sampleSetItem_with_values(request, user, sample, new_attributeValue_dict)

    return True, None


def _create_or_update_sampleAttributes_for_sampleSetItem_with_dict(request, user, sample, sampleAttribute_dict):
    """
    sampleAttribute_dict has the attribute name be the key
    """

    logger.debug("ENTER views_helper._create_or_update_sampleAttributes_for_sampleSetItem_with_dict - sampleAttribute_dict=%s" % (sampleAttribute_dict))

    new_attributeValue_dict = {}

    if sampleAttribute_dict:
        attribute_objs = SampleAttribute.objects.all()
        for attribute_obj in attribute_objs:
            value = sampleAttribute_dict.get(attribute_obj.displayedName, "")
            if (value):
                isValid, errorMessage = sample_validator.validate_sampleAttribute(attribute_obj, value.encode('utf8'))
                if not isValid:
                    return isValid, errorMessage

                new_attributeValue_dict[attribute_obj.id] = value.encode('utf8')

        logger.debug("views_helper._create_or_update_sampleAttributes_for_sampleSetItem_with_dict - new_attributeValue_dict=%s" % (new_attributeValue_dict))

    _create_or_update_sampleAttributes_for_sampleSetItem_with_values(request, user, sample, new_attributeValue_dict)

    isValid = True
    return isValid, None


def _create_or_update_sampleAttributes_for_sampleSetItem_with_values(request, user, sample, new_attributeValue_dict):
    if new_attributeValue_dict:
        currentDateTime = timezone.now()  ##datetime.datetime.now()

        # logger.debug("views_helper - ENTER new_attributeValue_dict=%s" %(new_attributeValue_dict))

        for key, newValue in new_attributeValue_dict.items():
            sampleAttribute_objs = SampleAttribute.objects.filter(id=key)

            logger.debug("views_helper._create_or_update_sampleAttributes_for_sampleSetItem_with_values() #3 sampleAttribute_objs.count=%d" % (sampleAttribute_objs.count()))

            if sampleAttribute_objs.count() > 0:
                if newValue:

                    attributeValue_kwargs = {
                        'value': newValue,
                        'creator': user,
                        'creationDate': currentDateTime,
                        'lastModifiedUser': user,
                        'lastModifiedDate': currentDateTime
                        }
                    attributeValue, isCreated = SampleAttributeValue.objects.get_or_create(sample=sample, sampleAttribute=sampleAttribute_objs[0], defaults=attributeValue_kwargs)

                    if not isCreated:
                        if attributeValue.value != newValue:
                            attributeValue.value = newValue
                            attributeValue.lastModifiedUser = user
                            attributeValue.lastModifiedDate = currentDateTime

                            attributeValue.save()
                            logger.debug("views_helper - _create_or_update_sampleAttributes_for_sampleSetItem_with_values - #4 UPDATED!! isCreated=%s attributeValue.id=%d; value=%s" % (str(isCreated), attributeValue.id, newValue))
                    else:
                        logger.debug("views_helper - _create_or_update_sampleAttributes_for_sampleSetItem_with_values - #5 existing attributeValue!! attributeValue.id=%d; value=%s" % (attributeValue.id, newValue))
                else:
                    existingAttributeValues = SampleAttributeValue.objects.filter(sample=sample, sampleAttribute=sampleAttribute_objs[0])

                    logger.debug("views_helper._create_or_update_sampleAttributes_for_sampleSetItem_with_values() #6 existingAttributeValues.count=%d" % (existingAttributeValues.count()))

                    if (existingAttributeValues.count() > 0):
                        existingAttributeValue = existingAttributeValues[0]
                        existingAttributeValue.value = newValue
                        existingAttributeValue.lastModifiedUser = user
                        existingAttributeValue.lastModifiedDate = currentDateTime

                        existingAttributeValue.save()
                        logger.debug("views_helper - _create_or_update_sampleAttributes_for_sampleSetItem_with_values - #7 UPDATED with None!! attributeValue.id=%d;" % (attributeValue.id))


def _create_or_update_pending_sampleSetItem(request, user, sampleSet_ids, sample, sampleGender, sampleRelationshipRole, sampleRelationshipGroup, sampleControlType,
        selectedBarcodeKit, selectedBarcode, sampleCancerType, sampleCellularityPct, sampleNucleotideType,
        pcrPlateRow, sampleBiopsyDays, sampleCellNum, sampleCoupleId, sampleEmbryoId, sampleSetItemDescription):

    if selectedBarcode:
        dnabarcode = models.dnaBarcode.objects.get(name=selectedBarcodeKit, id_str=selectedBarcode)
    else:
        dnabarcode = None

    if sampleNucleotideType.lower() == "fusions":
        sampleNucleotideType = "rna"

    for sampleSet_id in sampleSet_ids:
        sampleSet = get_object_or_404(SampleSet, pk=sampleSet_id)
        relationshipGroup = int(sampleRelationshipGroup) if sampleRelationshipGroup else 0
        pcrPlateColumn = "1" if pcrPlateRow else ""

        sampleSetItem_kwargs = {
            'gender': sampleGender,
            'relationshipRole': sampleRelationshipRole,
            'relationshipGroup': relationshipGroup,
            'controlType': sampleControlType,
            'cancerType': sampleCancerType,
            'cellularityPct': sampleCellularityPct,
            'dnabarcode': dnabarcode,
            'pcrPlateRow': pcrPlateRow,
            'pcrPlateColumn': pcrPlateColumn,
            'biopsyDays': sampleBiopsyDays,
            'cellNum': sampleCellNum,
            'coupleId': sampleCoupleId,
            'embryoId': sampleEmbryoId,
            'description': sampleSetItemDescription,
            'lastModifiedUser': user,
        }
        try:
            sampleSetItem = SampleSetItem.objects.get(sample=sample, sampleSet_id=sampleSet_id, nucleotideType=sampleNucleotideType, dnabarcode=dnabarcode)
        except:
            sampleSetItem = SampleSetItem(sample=sample, sampleSet_id=sampleSet_id, nucleotideType=sampleNucleotideType, creator=user)

        for field, value in sampleSetItem_kwargs.iteritems():
            setattr(sampleSetItem, field, value)
        sampleSetItem.save()


def _create_or_update_sampleSetItem(request, user, sample):
    currentDateTime = timezone.now()  ##datetime.datetime.now()

    queryDict = request.POST
    sampleSetItem_id = queryDict.get("id", None)

    gender = queryDict.get("gender", "")
    relationshipRole = queryDict.get("relationshipRole", "")
    relationshipGroup = queryDict.get("relationshipGroup", None)
    sampleSetItemDescription = queryDict.get("sampleDescription", "")
    sampleSetItem = get_object_or_404(SampleSetItem, pk=sampleSetItem_id)

    selectedBarcodeKitName = queryDict.get("barcodeKit", "").strip()
    selectedBarcode = queryDict.get("barcode", "").strip()

    controlType = queryDict.get("controlType", "")
    cancerType = queryDict.get("cancerType", "")
    cellularityPct = queryDict.get("cellularityPct", None)
    if cellularityPct == "":
        cellularityPct = None

    selectedDnaBarcode = None
    if selectedBarcodeKitName and selectedBarcode:
        selectedDnaBarcode = models.dnaBarcode.objects.get(name=selectedBarcodeKitName, id_str=selectedBarcode)

    selectedNucleotideType = queryDict.get("nucleotideType", "").strip()
    if selectedNucleotideType.lower() == "fusions":
        selectedNucleotideType = "rna"

    pcrPlateRow = queryDict.get("pcrPlateRow", "").strip()
    pcrPlateColumn = "1" if pcrPlateRow else ""

    sampleBiopsyDays = queryDict.get("biopsyDays", "0")
    sampleCellNum = queryDict.get("cellNum", "")
    sampleCoupleId = queryDict.get("coupleId", "")
    sampleEmbryoId = queryDict.get("embryoId", "")

    isValid, errorMessage = sample_validator.validate_samplesetitem_update_for_existing_sampleset(sampleSetItem, sample, selectedDnaBarcode, selectedNucleotideType, pcrPlateRow)
    if isValid:
        sampleSetItem_kwargs = {
            'gender': gender,
            'relationshipRole': relationshipRole,
            'relationshipGroup': relationshipGroup,
            'dnabarcode': selectedDnaBarcode,
            'controlType': controlType,
            'cancerType': cancerType,
            'cellularityPct': cellularityPct,
            'nucleotideType': selectedNucleotideType,
            'pcrPlateRow': pcrPlateRow,
            'pcrPlateColumn': pcrPlateColumn,
            'biopsyDays': sampleBiopsyDays if sampleBiopsyDays else "0",
            'cellNum': sampleCellNum,
            'coupleId': sampleCoupleId,
            'embryoId': sampleEmbryoId,
            'description': sampleSetItemDescription,
            'lastModifiedUser': user,
            'lastModifiedDate': currentDateTime
            }
        for field, value in sampleSetItem_kwargs.iteritems():
            setattr(sampleSetItem, field, value)

        logger.debug("views_helper._create_or_update_sampleSetItem sampleSetItem_kwargs=%s" % (sampleSetItem_kwargs))

        sampleSetItem.save()
        logger.debug("views_helper - _create_or_update_sampleSetItem UPDATED for sampleSetItem.id=%d" % (sampleSetItem.id))
        return True, None
    else:
        return isValid, errorMessage


def _get_nucleotideType_choices(sampleGroupType=""):
    nucleotideType_choices = []
    for internalValue, displayedValue in SampleSetItem.get_nucleotideType_choices():
        if internalValue == "rna" and "fusions" in sampleGroupType.lower():
            continue
        else:
            nucleotideType_choices.append((internalValue, displayedValue))

    if "fusions" in sampleGroupType.lower() or not sampleGroupType:
        nucleotideType_choices.append(('fusions', 'Fusions'))

    return nucleotideType_choices


def _get_pcrPlateRow_choices(request):
    row_choices_tuple = SampleSetItem.get_ampliseq_plate_v1_row_choices()
    row_choices = OrderedDict()
    for i, (internalValue, displayedValue) in enumerate(row_choices_tuple):
        row_choices[internalValue] = displayedValue

    return row_choices


def _get_pcrPlateRow_valid_values(request):
    row_choices_tuple = SampleSetItem.get_ampliseq_plate_v1_row_choices()
    row_values = []
    for i, (internalValue, displayedValue) in enumerate(row_choices_tuple):
        row_values.append(displayedValue)

    return row_values


def _get_pcrPlateCol_valid_values(request):
    col_choices_tuple = SampleSetItem.get_ampliseq_plate_v1_column_choices()
    col_values = []
    for i, (internalValue, displayedValue) in enumerate(col_choices_tuple):
        col_values.append(displayedValue)

    return col_values


def _get_libraryPrepType_choices(request):
    choices_tuple = SampleSet.ALLOWED_LIBRARY_PREP_TYPES
    choices = OrderedDict()
    for i, (internalValue, displayedValue) in enumerate(choices_tuple):
        choices[internalValue] = displayedValue
    return choices


def _get_sampleset_choices(request):
    choices_tuple = SampleSet.ALLOWED_SAMPLESET_STATUS
    choices = OrderedDict()
    for i, (internalValue, displayedValue) in enumerate(choices_tuple):
        choices[internalValue] = displayedValue

    return choices
