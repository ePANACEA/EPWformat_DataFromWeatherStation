# -\*- coding: utf-8 -\*-
'''
Created on 31 may. 2021

@author: mapas
'''
import re

from epanacea.weatherData import ComplexField, FileCsv


if __name__ == '__main__':
    fecha = ComplexField(rePattern = re.compile("(\d+)/(\d+)/(\d\d\d\d)(\d+):(\d+)"),\
                         listOfFields = ["Day","Month","Year","Hour","Minute"])
    
    atmospressure = ComplexField(operation = lambda x: x * 100,\
                         listOfFields = ["atmospressure"])
    
    fieldsList = [fecha,
                     "drybulb",
                     "relhum",
                     "glohorrad",
                     "sunshineduration",
                     "rain",
                     "windspd",
                     '',
                     'winddir',
                     atmospressure]
    
    metheo = FileCsv(path = r'C:\Users\mapas\workspace\epanacea\noDistribuir\Pamplona-GN\Pamplona2020.csv',
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