# -\*- coding: utf-8 -\*-
'''
Created on 31 may. 2021

@author: mapas
'''
import re

from epanacea.weatherData import ComplexField, FileCsv


if __name__ == '__main__':
    # Descarga datos:
    # http://meteo.navarra.es/estaciones/estacion_datos_m.cfm?IDEstacion=405&p_10=1&p_10=2&p_10=3&p_10=4&p_10=11&p_10=6&p_10=7&fecha_desde=1%2F1%2F2021&fecha_hasta=1%2F11%2F2021
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
                     'winddir']
    
    
    # Fichero meteo: r'C:\Users\mapas\workspace\epanacea\noDistribuir\Pamplona-UPNa\Upna2020.csv'
    # r'C:\Users\mapas\workspace\epanacea\noDistribuir\Pamplona-UPNa\Upna-Enero2021-Octubre2021-Diciembre2020.csv'
    metheo = FileCsv(path = r'C:\Users\mapas\workspace\epanacea\noDistribuir\Pamplona-UPNa\Upna2021.csv',
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