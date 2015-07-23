# Copyright (C) 2015 Ion Torrent Systems, Inc. All Rights Reserved
import time
from datetime import datetime
from django.core.urlresolvers import reverse
from django.test import LiveServerTestCase
from iondb.rundb.test import SeleniumTestCase

from selenium.webdriver.common.by import By

from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.remote_connection import LOGGER
import logging
logger = logging.getLogger(__name__)


import os

class TestCreateOcpPlansByTemplate(SeleniumTestCase):  

    @classmethod
    def setUpClass(cls):
        super(TestCreateOcpPlansByTemplate, cls).setUpClass()
        

    def test_create_ir_ocp_plan_from_scratch(self):
        """
        Test happy path - create an IR, barcoded OCP plan from scratch
        - default RNA reference section should show
        - both DNA & RNA reference info selected
        Verify what has been persisted in
        - barcodedSamples JSON
        """          
        self.open(reverse('page_plan_new_plan_from_code', args=(8,)))
           
        #test requires a default IR account be set and TS can establish connection with it
        #now we need to wait for the ajax call which loads the IR accounts to finish
        self.wd.wait_for_ajax()
   
        #select the Tumor_Normal Sample Grouping
        self.wd.find_element_by_xpath('//input[@name="sampleGrouping" and @value="6"]').click() #DNA_RNA
        #wait
        self.wd.wait_for_ajax()
           
        irworkflow = self.wd.find_element_by_xpath('//select[@name="irworkflow"]')
        #choose the second workflow option
        irworkflow.find_elements_by_tag_name('option')[1].click()#select the first non-Upload Only OCP workflow
        time.sleep(3)
          
        #now navigate to the Kits chevron and choose the Chip-Type
        self.wd.wait_for_css("#Kits").find_elements_by_tag_name('a')[0].click()
        #self.wd.wait_for_css("#chipType").find_elements_by_tag_name('option')[6].click()#Ion 318v2 Chip
        self.wd.find_element_by_xpath("//select[@name='chipType']/option[@value='550']").click()
        
        self.wd.find_element_by_id("OneTouch__templatekitType").click()
        self.wd.wait_for_css("#templateKit").find_elements_by_tag_name('option')[1].click() ##ION PGM Template OT2 200 Kit
        self.wd.wait_for_css("#barcodeId").find_elements_by_tag_name('option')[1].click()#IonSet1
                   
        #now navigate to the Plan chevron
        self.wd.wait_for_css("#Save_plan").find_elements_by_tag_name('a')[0].click()
         
        #select ecoli for dna reference
        #self.wd.find_element_by_id("default_reference").find_elements_by_tag_name('option')[0].click() ##None
        select = Select(self.wd.find_element_by_id("default_reference"))
        select.select_by_visible_text("e_coli_dh10b(E. coli DH10B)")
         
        select = Select(self.wd.find_element_by_id("default_targetBedFile"))
        select.select_by_visible_text("ecoli.bed")
         
        ##select = Select(self.wd.find_element_by_id("default_hotSpotBedFile"))
        ##select.select_by_visible_text("ecoli_hotspot.bed")
         
        #select ecoli for rna reference
        select = Select(self.wd.find_element_by_id("mixedTypeRNA_reference"))
        select.select_by_visible_text("e_coli_dh10b(E. coli DH10B)")
        
        #uncheck the same reference for all samples
        if self.wd.find_element_by_id("isSameRefInfoPerSample").is_selected():
            self.wd.find_element_by_id("isSameRefInfoPerSample").click()
       
        #RNA sample not auto-populate
        if self.wd.find_element_by_id("isOncoSameSample").is_selected():
            self.wd.find_element_by_id("isOncoSameSample").click()
        #time.sleep(2)
        
        #clear and change number of samples
        self.wd.find_element_by_id("numRows").send_keys(Keys.CONTROL + "a")
        self.wd.find_element_by_id("numRows").send_keys(Keys.BACKSPACE)
        self.wd.find_element_by_id("numRows").send_keys('7')
        self.wd.find_element_by_id("numRowsClick").click()
        
        #now enter 4 samples
        sample_name_1 = 'ocp-Sample-Name-10'
        sample_ext_id_1 = 'ocp-Sample-External-Id-10'
        sample_description_1 = 'ocp-Sample-Desc-10'
   
        barcodedSampleTable = self.wd.find_element_by_id("chipsets")           
        trs = barcodedSampleTable.find_elements(By.TAG_NAME, "tr")            
        tds = trs[1].find_elements(By.TAG_NAME, "td")
           
        #logger.info( "test_create_ir_ocp_plan_from_scratch... tds[1]=%s" %(tds))          
        for element in tds:
            if element.find_elements(By.NAME, "sampleName"):
                #clear auto-generated sample name first
                element.find_element_by_name("sampleName").clear()
                element.find_element_by_name("sampleName").send_keys(sample_name_1+"1")
            if element.find_elements(By.NAME, "sampleExternalId"):
                element.find_element_by_name("sampleExternalId").send_keys(sample_ext_id_1)
            if element.find_elements(By.NAME, "sampleDescription"):
                element.find_element_by_name("sampleDescription").send_keys(sample_description_1)
            if element.find_elements(By.NAME,"nucleotideType"):
                element.find_element_by_xpath("//select[@name='nucleotideType']/option[@value='DNA']").click()
            if element.find_elements(By.NAME,"reference"):
                element.find_element_by_xpath("//select[@name='reference']/option[@value='hg19']").click()
            if element.find_elements(By.NAME,"targetRegionBedFile"):
                select = Select(element.find_element_by_name("targetRegionBedFile"))
                select.select_by_visible_text("AmpliSeqExome.20141113.designed.bed")          
            #IR workflow-related configuration
            if element.find_elements(By.NAME, "ircancerType"):
                element.find_element_by_name("ircancerType").find_elements_by_tag_name('option')[1].click()#Bladder Cancer
            if element.find_elements(By.NAME, "ircellularityPct"):
                element.find_element_by_name("ircellularityPct").send_keys(Keys.CONTROL + "a")
                element.find_element_by_name("ircellularityPct").send_keys(Keys.BACKSPACE)
                element.find_element_by_name("ircellularityPct").send_keys("17")

            if element.find_elements(By.NAME, "irWorkflow"):
                element.find_element_by_name("irWorkflow").find_elements_by_tag_name('option')[1].click()#non-Upload Only workflow
   
            if element.find_elements(By.NAME, "irGender"):
                element.find_element_by_name("irGender").find_elements_by_tag_name('option')[1].click()#Male
            if element.find_elements(By.NAME, "irRelationRole"):
                element.find_element_by_name("irRelationRole").find_elements_by_tag_name('option')[1].click()#Self
                          
            if element.find_elements(By.NAME, "irSetID"):
                element.find_element_by_name("irSetID").send_keys("31")
        
        #sample 1 RNA type
        tds = trs[2].find_elements(By.TAG_NAME, "td")
        #logger.info( "test_create_ir_ocp_plan_from_scratch... tds[1]=%s" %(tds))          
        for element in tds:
            if element.find_elements(By.NAME, "sampleName"):
                #clear auto-generated sample name first
                element.find_element_by_name("sampleName").clear()
                element.find_element_by_name("sampleName").send_keys(sample_name_1+"2")
            if element.find_elements(By.NAME, "sampleExternalId"):
                element.find_element_by_name("sampleExternalId").send_keys(sample_ext_id_1)
            if element.find_elements(By.NAME, "sampleDescription"):
                element.find_element_by_name("sampleDescription").send_keys(sample_description_1)
            if element.find_elements(By.NAME,"nucleotideType"):
                element.find_element_by_xpath("//select[@name='nucleotideType']/option[@value='RNA']").click()
            if element.find_elements(By.NAME,"reference"):
                element.find_element_by_xpath("//select[@name='reference']/option[@value='hg19_ampliseq_transcriptome_ercc_v1']").click()
            if element.find_elements(By.NAME,"targetRegionBedFile"):
                select = Select(element.find_element_by_name("targetRegionBedFile"))
                select.select_by_visible_text("hg19_AmpliSeq_Transcriptome_21K_v1.bed")          
            #IR workflow-related configuration
            if element.find_elements(By.NAME, "ircancerType"):
                element.find_element_by_name("ircancerType").find_elements_by_tag_name('option')[1].click()#Bladder Cancer
            if element.find_elements(By.NAME, "ircellularityPct"):
                element.find_element_by_name("ircellularityPct").send_keys(Keys.CONTROL + "a")
                element.find_element_by_name("ircellularityPct").send_keys(Keys.BACKSPACE)
                element.find_element_by_name("ircellularityPct").send_keys("17")

            if element.find_elements(By.NAME, "irWorkflow"):
                element.find_element_by_name("irWorkflow").find_elements_by_tag_name('option')[1].click()#non-Upload Only workflow
   
            if element.find_elements(By.NAME, "irGender"):
                element.find_element_by_name("irGender").find_elements_by_tag_name('option')[1].click()#Male
            if element.find_elements(By.NAME, "irRelationRole"):
                element.find_element_by_name("irRelationRole").find_elements_by_tag_name('option')[1].click()#Self
                          
            if element.find_elements(By.NAME, "irSetID"):
                element.find_element_by_name("irSetID").send_keys(Keys.CONTROL + "a")
                element.find_element_by_name("irSetID").send_keys(Keys.BACKSPACE)
                element.find_element_by_name("irSetID").send_keys("31")
        #wait
        #time.sleep(3)
        self.wd.wait_for_ajax() 

        sample_name_2 = 'ocp-Sample-Name-22'
        sample_ext_id_2 = 'ocp-Sample-External-Id-22'
        sample_description_2 = 'ocp-Sample-Desc-22'
           
        tds = trs[3].find_elements(By.TAG_NAME, "td")
           
        #logger.info( "test_create_ir_ocp_plan_from_scratch... tds[1]=%s" %(tds))          
        for element in tds:
            if element.find_elements(By.NAME, "sampleName"):
                #clear auto-generated sample name first
                element.find_element_by_name("sampleName").clear()
                element.find_element_by_name("sampleName").send_keys(sample_name_2+"1")
            if element.find_elements(By.NAME, "sampleExternalId"):
                element.find_element_by_name("sampleExternalId").send_keys(sample_ext_id_2)
            if element.find_elements(By.NAME, "sampleDescription"):
                element.find_element_by_name("sampleDescription").send_keys(sample_description_2)
            if element.find_elements(By.NAME,"nucleotideType"):
                element.find_element_by_xpath("//select[@name='nucleotideType']/option[@value='DNA']").click()
            if element.find_elements(By.NAME,"reference"):
                element.find_element_by_xpath("//select[@name='reference']/option[@value='hg19']").click()
            if element.find_elements(By.NAME,"targetRegionBedFile"):
                select = Select(element.find_element_by_name("targetRegionBedFile"))
                select.select_by_visible_text("AmpliSeqExome.20141113.designed.bed")          
            #IR workflow-related configuration
            if element.find_elements(By.NAME, "ircancerType"):
                element.find_element_by_name("ircancerType").find_elements_by_tag_name('option')[2].click()#Bladder Cancer
            if element.find_elements(By.NAME, "ircellularityPct"):
                element.find_element_by_name("ircellularityPct").send_keys(Keys.CONTROL + "a")
                element.find_element_by_name("ircellularityPct").send_keys(Keys.BACKSPACE)                
                element.find_element_by_name("ircellularityPct").send_keys("13")

            if element.find_elements(By.NAME, "irWorkflow"):
                element.find_element_by_name("irWorkflow").find_elements_by_tag_name('option')[1].click()#non-Upload Only workflow
   
            if element.find_elements(By.NAME, "irGender"):
                element.find_element_by_name("irGender").find_elements_by_tag_name('option')[1].click()#Male
            if element.find_elements(By.NAME, "irRelationRole"):
                element.find_element_by_name("irRelationRole").find_elements_by_tag_name('option')[1].click()#Self
                          
            if element.find_elements(By.NAME, "irSetID"):
                element.find_element_by_name("irSetID").send_keys(Keys.CONTROL + "a")
                element.find_element_by_name("irSetID").send_keys(Keys.BACKSPACE)
                element.find_element_by_name("irSetID").send_keys("52")

        sample_name_2 = 'ocp-Sample-Name-02'
        sample_ext_id_2 = 'ocp-Sample-External-Id-02'
        sample_description_2 = 'ocp-Sample-Desc-02'
           
        tds = trs[4].find_elements(By.TAG_NAME, "td")
           
        #logger.info( "test_create_ir_ocp_plan_from_scratch... tds[1]=%s" %(tds))          
        for element in tds:
            if element.find_elements(By.NAME, "sampleName"):
                #clear auto-generated sample name first
                element.find_element_by_name("sampleName").clear()
                element.find_element_by_name("sampleName").send_keys(sample_name_2+"2")
            if element.find_elements(By.NAME, "sampleExternalId"):
                element.find_element_by_name("sampleExternalId").send_keys(sample_ext_id_1)
            if element.find_elements(By.NAME, "sampleDescription"):
                element.find_element_by_name("sampleDescription").send_keys(sample_description_1)
            if element.find_elements(By.NAME,"nucleotideType"):
                element.find_element_by_xpath("//select[@name='nucleotideType']/option[@value='DNA']").click()
            if element.find_elements(By.NAME,"reference"):
                element.find_element_by_xpath("//select[@name='reference']/option[@value='hg19']").click()
            if element.find_elements(By.NAME,"targetRegionBedFile"):
                select = Select(element.find_element_by_name("targetRegionBedFile"))
                select.select_by_visible_text("CCP.20131001.designed.bed")          
            #IR workflow-related configuration
            if element.find_elements(By.NAME, "ircancerType"):
                element.find_element_by_name("ircancerType").find_elements_by_tag_name('option')[1].click()#Bladder Cancer
            if element.find_elements(By.NAME, "ircellularityPct"):
                element.find_element_by_name("ircellularityPct").send_keys(Keys.CONTROL + "a")
                element.find_element_by_name("ircellularityPct").send_keys(Keys.BACKSPACE)                    
                element.find_element_by_name("ircellularityPct").send_keys("5")

            if element.find_elements(By.NAME, "irWorkflow"):
                element.find_element_by_name("irWorkflow").find_elements_by_tag_name('option')[1].click()#non-Upload Only workflow
   
            if element.find_elements(By.NAME, "irGender"):
                element.find_element_by_name("irGender").find_elements_by_tag_name('option')[1].click()#Male
            if element.find_elements(By.NAME, "irRelationRole"):
                element.find_element_by_name("irRelationRole").find_elements_by_tag_name('option')[1].click()#Self
                          
            if element.find_elements(By.NAME, "irSetID"):
                element.find_element_by_name("irSetID").send_keys(Keys.CONTROL + "a")
                element.find_element_by_name("irSetID").send_keys(Keys.BACKSPACE)
                element.find_element_by_name("irSetID").send_keys("52")
                
        sample_name_3 = 'ocp-Sample-Name-3'                
        sample_ext_id_3 = 'ocp-Sample-External-Id-3'
        sample_description_3 = 'ocp-Sample-Desc-3'        
        tds = trs[5].find_elements(By.TAG_NAME, "td")
           
        #logger.info( "test_create_ir_ocp_plan_from_scratch... tds[1]=%s" %(tds))          
        for element in tds:
            if element.find_elements(By.NAME, "sampleName"):
                #clear auto-generated sample name first
                element.find_element_by_name("sampleName").clear()
                element.find_element_by_name("sampleName").send_keys(sample_name_3)
            if element.find_elements(By.NAME, "sampleExternalId"):
                element.find_element_by_name("sampleExternalId").send_keys(sample_ext_id_3)
            if element.find_elements(By.NAME, "sampleDescription"):
                element.find_element_by_name("sampleDescription").send_keys(sample_description_3)
            if element.find_elements(By.NAME,"nucleotideType"):
                element.find_element_by_xpath("//select[@name='nucleotideType']/option[@value='DNA']").click()
            if element.find_elements(By.NAME,"reference"):
                element.find_element_by_xpath("//select[@name='reference']/option[@value='hg19']").click()
            if element.find_elements(By.NAME,"targetRegionBedFile"):
                select = Select(element.find_element_by_name("targetRegionBedFile"))
                select.select_by_visible_text("AmpliSeqExome.20131001.designed.bed")          
            #IR workflow-related configuration
            if element.find_elements(By.NAME, "ircancerType"):
                element.find_element_by_name("ircancerType").find_elements_by_tag_name('option')[1].click()#Bladder Cancer
            if element.find_elements(By.NAME, "ircellularityPct"):
                element.find_element_by_name("ircellularityPct").send_keys("23")

            if element.find_elements(By.NAME, "irWorkflow"):
                element.find_element_by_name("irWorkflow").find_elements_by_tag_name('option')[1].click()#non-Upload Only workflow
   
            if element.find_elements(By.NAME, "irGender"):
                element.find_element_by_name("irGender").find_elements_by_tag_name('option')[1].click()#Male
            if element.find_elements(By.NAME, "irRelationRole"):
                element.find_element_by_name("irRelationRole").find_elements_by_tag_name('option')[1].click()#Self
                          
            if element.find_elements(By.NAME, "irSetID"):
                element.find_element_by_name("irSetID").send_keys("3")  

        sample_name_4 = 'ocp-Sample-Name-4'
        sample_ext_id_4 = 'ocp-Sample-External-Id-4'
        sample_description_4 = 'ocp-Sample-Desc-4'        
        tds = trs[6].find_elements(By.TAG_NAME, "td")
           
        #logger.info( "test_create_ir_ocp_plan_from_scratch... tds[1]=%s" %(tds))          
        for element in tds:
            if element.find_elements(By.NAME, "sampleName"):
                #clear auto-generated sample name first
                element.find_element_by_name("sampleName").clear()
                element.find_element_by_name("sampleName").send_keys(sample_name_4)
            if element.find_elements(By.NAME, "sampleExternalId"):
                element.find_element_by_name("sampleExternalId").send_keys(sample_ext_id_4)
            if element.find_elements(By.NAME, "sampleDescription"):
                element.find_element_by_name("sampleDescription").send_keys(sample_description_4)
            if element.find_elements(By.NAME,"nucleotideType"):
                element.find_element_by_xpath("//select[@name='nucleotideType']/option[@value='DNA']").click()
            if element.find_elements(By.NAME,"reference"):
                element.find_element_by_xpath("//select[@name='reference']/option[@value='hg19']").click()
            if element.find_elements(By.NAME,"targetRegionBedFile"):
                select = Select(element.find_element_by_name("targetRegionBedFile"))
                select.select_by_visible_text("AmpliSeqExome.20141113.designed.bed")          
            #IR workflow-related configuration
            if element.find_elements(By.NAME, "ircancerType"):
                element.find_element_by_name("ircancerType").find_elements_by_tag_name('option')[1].click()#Bladder Cancer
            if element.find_elements(By.NAME, "ircellularityPct"):
                element.find_element_by_name("ircellularityPct").send_keys("11")

            if element.find_elements(By.NAME, "irWorkflow"):
                element.find_element_by_name("irWorkflow").find_elements_by_tag_name('option')[1].click()#non-Upload Only workflow
   
            if element.find_elements(By.NAME, "irGender"):
                element.find_element_by_name("irGender").find_elements_by_tag_name('option')[1].click()#Male
            if element.find_elements(By.NAME, "irRelationRole"):
                element.find_element_by_name("irRelationRole").find_elements_by_tag_name('option')[1].click()#Self
                          
            if element.find_elements(By.NAME, "irSetID"):
                element.find_element_by_name("irSetID").send_keys("41")  
                              
        sample_name_5 = 'ocp-Sample-Name-05'
        sample_ext_id_5 = 'ocp-Sample-External-Id-05'
        sample_description_5 = 'ocp-Sample-Desc-05'
          
        tds = trs[7].find_elements(By.TAG_NAME, "td")
           
        #logger.info( "test_create_ir_ocp_plan_from_scratch... tds[1]=%s" %(tds))          
        for element in tds:
            if element.find_elements(By.NAME, "sampleName"):
                #clear auto-generated sample name first
                element.find_element_by_name("sampleName").clear()
                element.find_element_by_name("sampleName").send_keys(sample_name_5)
            if element.find_elements(By.NAME, "sampleExternalId"):
                element.find_element_by_name("sampleExternalId").send_keys(sample_ext_id_5)
            if element.find_elements(By.NAME, "sampleDescription"):
                element.find_element_by_name("sampleDescription").send_keys(sample_description_5)
            if element.find_elements(By.NAME,"nucleotideType"):
                element.find_element_by_xpath("//select[@name='nucleotideType']/option[@value='RNA']").click()
            if element.find_elements(By.NAME,"reference"):
                element.find_element_by_xpath("//select[@name='reference']/option[@value='e_coli_dh10b']").click()
            if element.find_elements(By.NAME,"targetRegionBedFile"):
                select = Select(element.find_element_by_name("targetRegionBedFile"))
                select.select_by_visible_text("ecoli.bed")          
            #IR workflow-related configuration
            if element.find_elements(By.NAME, "ircancerType"):
                element.find_element_by_name("ircancerType").find_elements_by_tag_name('option')[1].click()#Bladder Cancer
            if element.find_elements(By.NAME, "ircellularityPct"):
                element.find_element_by_name("ircellularityPct").send_keys("42")

            if element.find_elements(By.NAME, "irWorkflow"):
                element.find_element_by_name("irWorkflow").find_elements_by_tag_name('option')[1].click()#non-Upload Only workflow
   
            if element.find_elements(By.NAME, "irGender"):
                element.find_element_by_name("irGender").find_elements_by_tag_name('option')[1].click()#Male
            if element.find_elements(By.NAME, "irRelationRole"):
                element.find_element_by_name("irRelationRole").find_elements_by_tag_name('option')[1].click()#Self
                          
            if element.find_elements(By.NAME, "irSetID"):
                element.find_element_by_name("irSetID").send_keys("5")                
        #enter notes for the plan
        PLAN_NOTES = 'this is a selenium test ocp plan'
        self.wd.find_element_by_id("note").clear()  #clear notes first
        self.wd.find_element_by_id("note").send_keys(PLAN_NOTES)
        time.sleep(3)
        
        current_dt = datetime.strftime(datetime.now(), '%Y-%m-%d-%H-%M-%S')
        self.wd.find_element_by_id("planName").send_keys('autoTest-ocp-plan-{0}'.format(current_dt))
         
        #now save the plan
        self.wd.find_element_by_xpath('//a[@class="btn btn-primary btn-100 pull-right"]').click()
        self.wd.wait_for_ajax()
        
        time.sleep(30)
        return
        #now retrieve the latest PlannedExperiment (The Plan you just saved) and verify the data you entered
        ocp_plan = self.get_latest_planned_experiment()
   
        logger.info(">>> test_create_ir_ocp_plan_from_scratch plan_id=%d" %(ocp_plan["id"]))
        time.sleep(3)
           
        #verify the barcoded samples
        self.assertEqual(len(ocp_plan['barcodedSamples']), 1)
        barcodes = ocp_plan['barcodedSamples'].keys()

        logger.info(">>> test_create_ir_ocp_plan_from_scratch...  barcodedSamples.keys=%s" %(barcodes))
          
        if sample_name_1 in barcodes:
            self.assertTrue(True)
        else:
            self.assertTrue(False)
   
        sample1 = ocp_plan['barcodedSamples'][sample_name_1]
        barcodedSamples = sample1['barcodeSampleInfo']
           
        logger.info( "test_create_ir_ocp_plan_from_scratch... ASSERT.... barcodedSample1 - barcodeSampleInfo=%s" %(barcodedSamples))
                       
        _ionSet1Dict = barcodedSamples['IonSelect-1']
        self.assertEqual(_ionSet1Dict['description'], sample_description_1)
        self.assertEqual(_ionSet1Dict['externalId'], sample_ext_id_1)
        
        if "DNA" in _ionSet1Dict['nucleotideType']:
            self.assertTrue(True)
        else:
            self.assertTrue(False)
        
        _ionSet2Dict = barcodedSamples['IonSelect-2']
        if "RNA" in _ionSet2Dict['nucleotideType']:
            self.assertTrue(True)
        else:
            self.assertTrue(False)
   
        #now examine the selectedPlugins blob for IonReporterUploader
        selected_plugins = ocp_plan['selectedPlugins']
   
        logger.info( "test_create_ir_ocp_plan_from_scratch... selected_plugins=%s" %(selected_plugins))
   
        if 'IonReporterUploader' in selected_plugins:
            iru = selected_plugins['IonReporterUploader']
            if 'userInput' in iru:
                ui = iru['userInput']
                if 'userInputInfo' in ui:
                    uii = ui['userInputInfo']
                    if len(uii) != 2: self.assertTrue(False)
   
                    index = 0
                    for _d in uii:
                        index += 1
                        #make sure all the keys are in each dictionary of the userInputInfo list
                        if not 'ApplicationType' in _d or not 'Gender' in _d or not 'Relation' in _d\
                            or not 'RelationRole' in _d or not 'Workflow' in _d or not 'barcodeId' in _d or not 'sample' in _d \
                            or not 'sampleDescription' in _d or not 'sampleExternalId' in _d or not 'sampleName' in _d \
                            or not 'setid' in _d:
                            self.assertTrue(False)
   
                        #make sure the set id has the suffix
                        if not '__' in _d['setid']: self.assertTrue(False)
   
                        if index == 1:
                            #check the sample name
                            if _d['sample'] != sample_name_1 or _d['sampleName'] != sample_name_1: self.assertTrue(False)
#                            #check the gender, relation and relationRole
#                            if _d['Gender'] != 'Male' or _d['Relation'] != 'Tumor_Normal' or _d['RelationRole'] != 'Tumor': self.assertTrue(False)
                            #check the gender and relationRole
                            if _d['Gender'] != 'Male' or _d['RelationRole'] != 'Self': self.assertTrue(False)
                            #check the barcodeId
                            if _d['barcodeId'] != 'IonSelect-1': self.assertTrue(False)   
   
            else:
                self.assertTrue(False)
        else:
            self.assertTrue(False)
   
        #now delete the planned run
        logger.info( "test_create_ir_ocp_plan_from_scratch... GOING to delete plan.id=%s" %(ocp_plan['id']))
           
        self.delete_planned_experiment(ocp_plan['id']) 
        time.sleep(2)
 