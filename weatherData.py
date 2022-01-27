# -\*- coding: utf-8 -\*-
'''
Created on 15 may. 2021

@author: mapas
'''
from datetime import datetime
import re

from lxml import etree
import matplotlib.pyplot as plt
from matplotlib import cm
from pvlib import irradiance,location
import pandas as pd
import numpy as np
import math
import os
import sys

from metpy.units import units
from metpy.calc import dewpoint_from_relative_humidity,add_height_to_pressure

import calendar

def getListOfValidVariableNames():
    tree = etree.parse('epanaceaWeatherDataSchema10.xsd')
    listOfValueElements=tree.xpath("//xs:simpleType[@name='variableName']/xs:restriction/xs:pattern",namespaces={'xs': 'http://www.w3.org/2001/XMLSchema'})
    return [element.attrib['value'] for element in listOfValueElements]

def getListOfValidTimeNames():
    tree = etree.parse('epanaceaWeatherDataSchema10.xsd')
    listOfTimeElements=tree.xpath("//xs:complexType[@name='DataType']/xs:all/xs:element[@name='Time']/xs:complexType/xs:choice/xs:sequence/xs:element",namespaces={'xs': 'http://www.w3.org/2001/XMLSchema'})
    return [element.attrib['name'] for element in listOfTimeElements]

listOfValidVariableNames = getListOfValidVariableNames()
listOfValidTimeNames = getListOfValidTimeNames()


def skyEmissivity(dewPoint,opaqueSkyCover):
    dewPoint += 273.0
    emi = (0.787 + 0.764 * math.log(dewPoint/273.0)) * ( 1 + 0.0224 * opaqueSkyCover -0.0035 * opaqueSkyCover**2 + 0.00028 * opaqueSkyCover**3 )
    return emi

def horizontalInfraredIntensity(skyEmi, drybulb):
    drybulb += 273.0
    ir = skyEmi * 5.67 * 10**-8 * drybulb**4
    return ir

def thirdSunday(month,year):
    c = calendar.Calendar(firstweekday=calendar.MONDAY)
    
    
    monthcal = c.monthdatescalendar(year,month)
    third = [day for week in monthcal for day in week if \
                    day.weekday() == calendar.SUNDAY and \
                    day.month == month][2]    
    return third
    

class ComplexField(object):
    def __init__(self,
                 rePattern = None,
                 operation = None,
                 listOfFields = []):
        self.rePattern = rePattern
        self.operation = operation
        self.listOfFields = listOfFields
        self.check()
        
    def check(self):
        if self.rePattern != None and self.rePattern.__class__ != re.Pattern:
            raise Exception("rePattern is not a valid rePattern")
        if self.listOfFields == []:
            raise Exception("listOfFields is empty")
        
        notFoundFields = [x for x in self.listOfFields if x not in listOfValidVariableNames + listOfValidTimeNames]
        if notFoundFields:
            raise Exception("Invalid field names: {0}".format(", ".join(notFoundFields)))
    def process(self,cell):
        if self.rePattern:
            m=self.rePattern.match(cell)
            if m:
                tupleList = []
                for indice,field in enumerate(self.listOfFields):
                    tupleList.append((field,m.group(indice+1)))
            else:
                raise Exception("Regular expression did not match the cell string")
        elif self.operation:
            tupleList = []
            for indice,field in enumerate(self.listOfFields):
                tupleList.append((field,self.operation(float(cell.replace('"','')))))
            
        
        return tupleList
    
class Variable(object):
    def __init__(self,**kwargs):
        self.dateTime = None
        for k in kwargs.keys():
            setattr(self, k, kwargs[k])
        self.procesa()
    
    def procesa(self):
        now = datetime.now()
        self.dateTime = datetime(int(self.Year) if hasattr(self, 'Year') else now.year, 
                                 int(self.Month) if hasattr(self, 'Month') else now.month, 
                                 int(self.Day) if hasattr(self, 'Day') else now.day, 
                                 hour=int(self.Hour) if hasattr(self, 'Hour') else 0 , 
                                 minute=int(self.Minute) if hasattr(self, 'Minute') else 0 ,
                                 tzinfo=None)
        
    
class FileCsv(object):
    def __init__(self,
                 path = r'',
                 listOfFields = [],
                 startingRow = 0,
                 endingRow= -1,
                 separator = ',',
                 longitude = 1.64,
                 latitude = 42.8,
                 altitude= 430.0,
                 city = 'Pamplona',
                 stateProv = 'Navarra',
                 country = 'ESP',
                 inTime = 1,
                 inWMO = 0):
        self.path = path
        self.listOfFields = listOfFields
        self.startingRow = startingRow
        self.endingRow = endingRow
        self.separator = separator
        self.content = []
        self.city = city 
        self.stateProv = stateProv
        self.longitude = longitude
        self.latitude = latitude
        self.altitude= altitude
        self.country = country
        self.inTime = inTime
        self.inWMO = inWMO
        self.fieldSource = ''
        self.check()
        
    @property
    def isLeap(self):
        februaryValues = self.getValues('drybulb',month=2)
        if februaryValues:
            year = februaryValues[0].dateTime.year 
            return calendar.isleap(year)
        else:
            return False
        
    def check(self):
        notFoundFields = [x for x in filter(lambda y: y.__class__ != ComplexField,self.listOfFields) if x!= "" and x not in listOfValidVariableNames + listOfValidTimeNames]
        if notFoundFields:
            raise Exception("Invalid field names: {0}".format(", ".join(notFoundFields)))                          
            
    def process(self):
        with open(self.path,'r') as csvFile:
            content = csvFile.read()
        lines = content.split('\n')[self.startingRow:self.endingRow]
        for l in lines:
            paramDict = {}
            for cellContent,variable in zip(l.split(self.separator),self.listOfFields):
                cellContent = cellContent.replace('"','')
                if variable.__class__ == ComplexField:
                    tupleList = variable.process(cellContent)
                    for key,value in tupleList:
                        try:
                            paramDict[key] = float(value)
                        except:
                            paramDict[key] = value
                elif variable == "":
                    continue
                else:
                    try:
                        paramDict[variable] = float(cellContent)
                    except:
                        paramDict[variable] = cellContent
                    
            timeKeys = [x for x in paramDict.keys() if x in ['Day','Month','Year','Hour','Minute']]
            timeDict = {}
            for k in timeKeys:
                timeDict[k] = paramDict[k]
                del paramDict[k]
                
            for k in paramDict.keys():
                newDict = {}
                newDict[k] = paramDict[k]
                auxDict = timeDict | newDict                        
                newRecord = Variable(**auxDict)
                self.content.append(newRecord)
                
        listOfFields = [] 
        for f in self.listOfFields:
            if f.__class__ == str:
                listOfFields.append(f)
            else:
                for f2 in f.listOfFields: 
                    listOfFields.append(f2)
        if 'atmospressure' not in listOfFields:            
            self.generateAtmosPressure()
                
        if 'opaqskycvr' not in listOfFields:
            self.generateOpaqueSkyCover()
        if 'totskycvr' not in listOfFields:            
            self.generateTotalSkyCover()
        if 'dewpoint' not in listOfFields:
            if 'drybulb' in listOfFields and 'relhum' in listOfFields:                                
                self.generateDewPoint()                
        if 'dirnorrad' not in listOfFields:
            if 'glohorrad' in listOfFields:
                self.generateDirintFromGhi()     
        if 'difhorzrad' not in listOfFields:
            self.generateDifuseHorizontalRadiation()     
                
        if 'horirsky' not in listOfFields:
            self.generateHorizontalInfrarredFromSky()
            
        if 'extdirrad' not in listOfFields:
            self.generateExtraterrestrialDirectNormalRadiation()
            
        if 'exthorzrad' not in listOfFields:
            self.generateExtraterrestrialHorizontalRadiation()                     
                      
    def getValues(self,variable,year=None,month=None,day=None):
        valueList = [x for x in self.content if hasattr(x, variable)]
        if year:
            valueList = [x for x in valueList if x.Year == year] 
        if month:
            valueList = [x for x in valueList if x.Month == month]      
        if day:
            valueList = [x for x in valueList if x.Day == day]                
                   
        valueList.sort(key = lambda x: x.dateTime)   
        return valueList
    
    def getValue(self,dateTime=None,variable = 'drybulb'):
        valueList = self.getValues(variable)
        value = next((x for x in valueList if x.dateTime == dateTime), None)
        if value:
            return getattr(value, variable)
    
    def timeSeries(self,default = 'drybulb'):
        valueList= self.getValues(default)
        serie = [x.dateTime for x in valueList]
        numberOfRecordsPerHour = len(list((filter(lambda x: x.Year == valueList[0].Year and x.Month == valueList[0].Month and x.Day == valueList[0].Day and x.Hour == valueList[0].Hour ,valueList))))
        return serie,numberOfRecordsPerHour
        
    
    def getMonthMeanValues(self,variable):
        result = []
        for index in range(1,13):
            monthValues = [getattr(x,variable) for x in self.getValues(variable,month = index)]
            avg = sum(monthValues) / len(monthValues) if len(monthValues) > 0 else 0
            result.append(avg)
        return result
    def getAnnualMeanValue(self,variable):
        monthly = self.getMonthMeanValues(variable)
        avg = sum(monthly) / len([x for x in monthly if x!= 0]) if len([x for x in monthly if x!= 0]) > 0 else 0
        return avg
        
        
    
    def plot(self,variable=[]):
        if variable.__class__ == str:
            variable = [variable]
        fig, ax = plt.subplots()
        n = len(variable)
        cmap = cm.get_cmap('Spectral')
        for i,v in enumerate(variable):
            if v not in listOfValidVariableNames:
                raise Exception("{0} is not a valid vaiable name".format(v))
            rgba = cmap(float(i)/n)
            valueList = self.getValues(v)
            x = [x.dateTime for x in valueList]
            y = [getattr(x,v) for x in valueList]
            plt.plot_date(x, y,color=rgba,linestyle='solid',marker='None')
        ax.legend(variable)
        plt.title(self.city)
        plt.show()
        
    def writeEpwFile(self):
        meanDrybulb = self.getAnnualMeanValue('drybulb')
        thirdSundayMarch = thirdSunday(3,2021).strftime("%m/%d")
        thirdSundayOctober = thirdSunday(10,2021).strftime("%m/%d")
        serie,numberOfRecordsPerHour = self.timeSeries()
        weekDay = serie[0].strftime("%A")
        startDate = serie[0].strftime("%m/%d")
        endDate = serie[-1].strftime("%m/%d")
        drybulbs = [x.drybulb for x in self.getValues('drybulb')]
        dewpoints = [x.dewpoint for x in self.getValues('dewpoint')]
        relhums = [x.relhum for x in self.getValues('relhum')]
        atmospressures = [x.atmospressure for x in self.getValues('atmospressure')]
        exthorzrads = [x.exthorzrad for x in self.getValues('exthorzrad')]
        extdirrads = [x.extdirrad if  exthorzrad> 0 else 0 for x,exthorzrad in zip(self.getValues('extdirrad'),exthorzrads)]
        horirskys = [x.horirsky for x in self.getValues('horirsky')]
        glohorrads = [x.glohorrad for x in self.getValues('glohorrad')]
        dirnorrads = [x.dirnorrad for x in self.getValues('dirnorrad')]
        difhorzrads = [x.difhorzrad for x in self.getValues('difhorzrad')]        
        winddirs = [x.winddir if x.winddir!=None else 999 for x in self.getValues('winddir') ]
        windspds = [x.windspd if x.windspd != None else 999 for x in self.getValues('windspd')]       
        rains = [x.rain if x.rain != None else 999 for x in self.getValues('rain')]       
        
        (ruta,fichero) = os.path.split(self.path)
        (nombreBase,extension) = os.path.splitext(fichero)
        rutaEpw = os.path.join(ruta,f"{nombreBase}.epw")
        with open(rutaEpw,'w') as f:
            f.write(f'LOCATION,{self.city},{self.stateProv},{self.country},{self.fieldSource},{self.inWMO},{self.latitude},{self.longitude},{self.inTime},{self.altitude}\n')
            f.write(f'DESIGN CONDITIONS,0\n')
            f.write(f'TYPICAL/EXTREME PERIODS,0\n')
            f.write(f'GROUND TEMPERATURES,1,2,,,,{meanDrybulb:0.2f},{meanDrybulb:0.2f},{meanDrybulb:0.2f},{meanDrybulb:0.2f},{meanDrybulb:0.2f},{meanDrybulb:0.2f},{meanDrybulb:0.2f},{meanDrybulb:0.2f},{meanDrybulb:0.2f},{meanDrybulb:0.2f},{meanDrybulb:0.2f},{meanDrybulb:0.2f}\n')
            f.write(f'HOLIDAYS/DAYLIGHT SAVINGS,{"Yes" if self.isLeap else "No"},{thirdSundayMarch},{thirdSundayOctober},0\n')
            f.write(f'COMMENTS 1,Generated by epanacea energyplus weather generator\n')
            f.write(f'COMMENTS 2,Ground temperatures generated using mean dry bulb air temperature.\n')
            f.write(f'DATA PERIODS,1,{numberOfRecordsPerHour},Data,{weekDay},{startDate},{endDate}\n')
#             for i in range(0,8784*6,6):
#                 time=serie[i]
            for i,time in enumerate(serie):                
                year = time.year
                month=time.month
                day = time.day
                hour = time.hour + 1
                minute = time.minute
                drybulb = drybulbs[i]
                dewpoint = dewpoints[i]
                relhum = relhums[i]
                atmospressure = atmospressures[i]
                exthorzrad = exthorzrads[i]
                extdirrad = extdirrads[i]
                horirsky = horirskys[i]
                glohorrad = glohorrads[i]
                dirnorrad = dirnorrads[i]
                difhorzrad = difhorzrads[i]
                globalHorizontalIlluminance = 999999
                directNormalIlluminance = 999999
                diffuseHorizontalIlluminace = 999999
                zenithLuminance = 9999
                winddir = winddirs[i]
                windspd = windspds[i]
                totalSkyCover = 99
                opaqueSkyCover = 99
                visibility = 9999
                ceilingHeigth = 99999
                presentWeatherObservation = 9
                presentWeatherCodes = 999999999
                precipitableWater = 999
                aerosolOpticalDepth = .999
                snowDepth = 999
                daysSinceLastSnow = 99
                albedo = 999
                rain = rains[i]
                liquidPrecipitationQuantity = 99
                
                
                
                f.write(f'{year},{month},{day},{hour},{minute},*?*?*?*?*?*?*?*?*?*?*?*?*?*?*?*?*?*?*?*?*?*?,{drybulb:.1f},{dewpoint:0.1f},\
{relhum:0.0f},{atmospressure:0.0f},{exthorzrad:0.0f},{extdirrad:0.0f},{horirsky:0.0f},{glohorrad:0.0f},{dirnorrad:0.0f},{difhorzrad:0.0f},\
{globalHorizontalIlluminance:0.0f},{directNormalIlluminance:0.0f},{diffuseHorizontalIlluminace:0.0f},{zenithLuminance:0.0f},\
{winddir:0.0f},{windspd:0.1f},{totalSkyCover:0.1f},{opaqueSkyCover:0.1f},{visibility},{ceilingHeigth},{presentWeatherObservation},\
{presentWeatherCodes},{precipitableWater},{aerosolOpticalDepth},{snowDepth},{daysSinceLastSnow},{albedo},{rain:0.1f},{liquidPrecipitationQuantity}\n')
        
    
    def generateDewPoint(self):
        valuesDryBulb = self.getValues('drybulb')        
        valuesRelHum = self.getValues('relhum')  
        for drybulb,relHum in zip(valuesDryBulb,valuesRelHum):
            print("instante: {}/{}/{} {}:{} - {} - {}".format(drybulb.Day,drybulb.Month,drybulb.Year,drybulb.Hour,drybulb.Minute,drybulb.drybulb,relHum.relhum))
            dewpoint = dewpoint_from_relative_humidity(drybulb.drybulb  * units.degC ,relHum.relhum * units.percent).magnitude
            dic = {'Year':drybulb.Year,
                   'Month': drybulb.Month,
                   'Day': drybulb.Day,
                   'Hour': drybulb.Hour,
                   'Minute': drybulb.Minute,
                   'dewpoint':dewpoint}
            nuevaVariable = Variable(**dic)
            self.content.append(nuevaVariable)           
            
    def generateAtmosPressure(self):
        valuesDryBulb = self.getValues('drybulb')       
        atmospressure =  float(add_height_to_pressure([101.3] * units.kPa, height = [430] * units.m).magnitude[0]*100.0)
        for drybulb in valuesDryBulb:
            dic = {'Year':drybulb.Year,
                   'Month': drybulb.Month,
                   'Day': drybulb.Day,
                   'Hour': drybulb.Hour,
                   'Minute': drybulb.Minute,
                   'atmospressure':atmospressure}
            nuevaVariable = Variable(**dic)
            self.content.append(nuevaVariable)   
            
#         self.plot(["atmospressure"])       
         
            
    def generateOpaqueSkyCover(self):
        valuesDryBulb = self.getValues('drybulb')  
        for drybulb in valuesDryBulb:
            opaqskycvr= 5.0
            dic = {'Year':drybulb.Year,
                   'Month': drybulb.Month,
                   'Day': drybulb.Day,
                   'Hour': drybulb.Hour,
                   'Minute': drybulb.Minute,
                   'opaqskycvr':opaqskycvr}
            nuevaVariable = Variable(**dic)
            self.content.append(nuevaVariable)     
    def generateTotalSkyCover(self):
        valuesDryBulb = self.getValues('drybulb')  
        for drybulb in valuesDryBulb:
            totskycvr= 5.0
            dic = {'Year':drybulb.Year,
                   'Month': drybulb.Month,
                   'Day': drybulb.Day,
                   'Hour': drybulb.Hour,
                   'Minute': drybulb.Minute,
                   'totskycvr':totskycvr}
            nuevaVariable = Variable(**dic)
            self.content.append(nuevaVariable)   
            
    def generateHorizontalInfrarredFromSky(self):
        valuesDryBulb = self.getValues('drybulb')        
        valuesDewPoint = self.getValues('dewpoint')   
        valuesOpaqueSkyCover = self.getValues('opaqskycvr')           
        
        
        for drybulb,dewpoint,opaqueSkyCover in zip(valuesDryBulb,valuesDewPoint,valuesOpaqueSkyCover):
            emi = skyEmissivity(dewpoint.dewpoint,opaqueSkyCover.opaqskycvr)
            horirsky = horizontalInfraredIntensity(emi, drybulb.drybulb)
            dic = {'Year':drybulb.Year,
                   'Month': drybulb.Month,
                   'Day': drybulb.Day,
                   'Hour': drybulb.Hour,
                   'Minute': drybulb.Minute,
                   'horirsky':horirsky}
            nuevaVariable = Variable(**dic)
            self.content.append(nuevaVariable)        
        

        
    def generateDirintFromGhi(self):
        loc = location.Location(self.latitude,self.longitude,altitude=self.altitude)
        valuesGhi = self.getValues('glohorrad')        
        valuesPressure = self.getValues('atmospressure')   
        valuesDewPoint = self.getValues('dewpoint')   
        
        times = pd.to_datetime([x.dateTime for x in valuesGhi])
        ghi = pd.Series([x.glohorrad for x in valuesGhi], index=times)
        
        solar_position = loc.get_solarposition(times)
        
        zenith = solar_position['apparent_zenith']
        pressure = pd.Series([x.atmospressure for x in valuesPressure], index=times)
        dewPoint = pd.Series([x.dewpoint for x in valuesDewPoint], index=times)
        dirint_data = irradiance.dirint(ghi, zenith, times, pressure=pressure,
                                        temp_dew=dewPoint)
        
        dirnorrad = [x if not np.isnan(x) else 0.0 for x in dirint_data ]
        for dni,glo in zip(dirnorrad,valuesGhi):
            dic = {'Year':glo.Year,
                   'Month': glo.Month,
                   'Day': glo.Day,
                   'Hour': glo.Hour,
                   'Minute': glo.Minute,
                   'dirnorrad':dni}
            nuevaVariable = Variable(**dic)
            self.content.append(nuevaVariable)
            
            
    def generateDifuseHorizontalRadiation(self):
        valuesGhi = self.getValues('glohorrad')
        ValuesDni = self.getValues('dirnorrad')
        times = pd.to_datetime([x.dateTime for x in valuesGhi])
        
        loc = location.Location(self.latitude,self.longitude,altitude=self.altitude)        
        solar_position = loc.get_solarposition(times)        
        zenith = solar_position['apparent_zenith']        
        
        
        for ghi,dni,z in zip(valuesGhi,ValuesDni,zenith):
            z = math.radians(z)
            difhorzrad = ghi.glohorrad - dni.dirnorrad * math.cos(z) if math.cos(z) > 0 else 0.0
            if difhorzrad < 0:
                raise Exception("Diffuse horizontal radiation negative")
            dic = {'Year':ghi.Year,
                   'Month': ghi.Month,
                   'Day': ghi.Day,
                   'Hour': ghi.Hour,
                   'Minute': ghi.Minute,
                   'difhorzrad':difhorzrad}
            nuevaVariable = Variable(**dic)
            self.content.append(nuevaVariable)                 
            
    def generateExtraterrestrialDirectNormalRadiation(self):
        valuesDryBulb = self.getValues('drybulb') 
        times = pd.to_datetime([x.dateTime for x in valuesDryBulb])
        
        dni_extra = irradiance.get_extra_radiation(times)
        for dni,drybulb in zip(dni_extra,valuesDryBulb):
            dic = {'Year':drybulb.Year,
                   'Month': drybulb.Month,
                   'Day': drybulb.Day,
                   'Hour': drybulb.Hour,
                   'Minute': drybulb.Minute,
                   'extdirrad':dni}
            nuevaVariable = Variable(**dic)
            self.content.append(nuevaVariable)        
            

    def generateExtraterrestrialHorizontalRadiation(self):
        valuesDryBulb = self.getValues('drybulb') 
        valuesExtDirRad = self.getValues('extdirrad') 
        times = pd.to_datetime([x.dateTime for x in valuesDryBulb])
        
        loc = location.Location(self.latitude,self.longitude,altitude=self.altitude)        
        solar_position = loc.get_solarposition(times)        
        zenith = solar_position['apparent_zenith']        
        
        
        for extDirRad,z in zip(valuesExtDirRad,zenith):
            z = math.radians(z)
            exthorzrad = extDirRad.extdirrad * math.cos(z) if math.cos(z) > 0 else 0.0
            dic = {'Year':extDirRad.Year,
                   'Month': extDirRad.Month,
                   'Day': extDirRad.Day,
                   'Hour': extDirRad.Hour,
                   'Minute': extDirRad.Minute,
                   'exthorzrad':exthorzrad}
            nuevaVariable = Variable(**dic)
            self.content.append(nuevaVariable)                   
        
    

# Descarga meteo navarra
# Pamplona GN:
# http://meteo.navarra.es/estaciones/estacion_datos_m.cfm?IDEstacion=455&p_10=1&p_10=2&p_10=3&p_10=4&p_10=11&p_10=6&p_10=7&p_10=50&fecha_desde=1%2F1%2F2017&fecha_hasta=1%2F1%2F2018               
# Pamplona UPNa:
# http://meteo.navarra.es/estaciones/estacion_datos_m.cfm?IDEstacion=405&p_10=1&p_10=2&p_10=3&p_10=4&p_10=11&p_10=6&p_10=7&p_10=50&fecha_desde=1%2F1%2F2017&fecha_hasta=1%2F1%2F2018

def zenith(longitude=1.6,latitude = 41,altitude=400):
    loc = location.Location(latitude,longitude,altitude=altitude)    
    times = pd.DataFrame(
        {'Hours': pd.date_range('2020-01-01', '2021-01-01', freq='1H', closed='left')}
     )
    times=pd.date_range('2020-01-01', '2021-01-01',  freq="1H")
    solar_position = loc.get_solarposition(times)
    
    zenith = solar_position['apparent_zenith']    
    
    print(len(times[12:-1:24]))
    plt.plot_date(times[12:-1:24], zenith[12:-1:24],color='r',linestyle='solid',marker='None')    
    plt.show()

if __name__ == '__main__': 
 
    date = ComplexField(rePattern = re.compile("(\d+)/(\d+)/(\d\d\d\d)(\d+):(\d+)"),\
                         listOfFields = ["Day","Month","Year","Hour","Minute"])
    
    atmospressure = ComplexField(operation = lambda x: x * 100,\
                         listOfFields = ["atmospressure"])
    
    fieldsList = [date,
                     "drybulb",
                     "relhum",
                     "glohorrad",
                     "sunshineduration",
                     "rain",
                     "windspd",
                     '',
                     'winddir',
                     atmospressure]
    
    metheo = FileCsv(path = r'C:\Users\mapas\workspace\epanacea\noDistribuir\Pamplona-GN\Pamplona2017.csv',
                     listOfFields = fieldsList,
                     startingRow = 2,
                     endingRow = -5)
    metheo.process()
#     print(f'{"Yes" if metheo.isLeap else "No"}')
#     print(metheo.getMonthMeanValues('drybulb'))
#     print(thirdSunday(10,2021))
    
    
        
        
    metheo.plot(["glohorrad",'dirnorrad','sunshineduration','difhorzrad'])   
    metheo.plot(["atmospressure"])       
    metheo.plot(["drybulb",'relhum','dewpoint']) 
    metheo.plot(["horirsky"]) 
    metheo.plot(["extdirrad","exthorzrad"]) 

    metheo.writeEpwFile()
    
    
        
    
    

