from flask import request, Flask, jsonify, abort
from flask_cors import CORS
import json

import engines.functions_timeseries as ft
import engines.BBDD as db
import os
from celery import Celery



# import engines functions_timeseries
from engines.helpers import merge_two_dicts
from engines.var import anomaly_VAR, univariate_anomaly_VAR,univariate_forecast_VAR
from engines.holtwinter import anomaly_holt,forecast_holt
from engines.auto_arima import anomaly_AutoArima
from engines.lstm import anomaly_LSTM, anomaly_uni_LSTM


server = Flask(__name__)
CORS(server)


server.config.from_pyfile(os.path.join(".", "config/app.cfg"), silent=False)

db.init_database()

DB_NAME= server.config.get("DB_NAME")
PORT = server.config.get("PORT")

# Celery configuration
server.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
server.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'

# Initialize Celery
celery = Celery(server.name, broker=server.config['CELERY_BROKER_URL'])
celery.conf.update(server.config)


@server.route('/univariate', methods=['POST'])
def univariate_engine():
    db.init_database()

    if not request.json:
        abort(400)


    timedata = request.get_json()
    print (timedata)
    lista=timedata['data']

    num_fut = int(timedata.get('num_future', 5))
    desv_mae = int(timedata.get('desv_metric', 2))
    name = timedata.get('name', 'NA')
    train = timedata.get('train', True)
    restart = timedata.get('restart', False)

    print ("train?"+ str(train))
    print ("restart?" + str(restart))
    print ("Received TS")


    if(name != 'NA'):
        filename= './lst/'+name+'.lst'
        try:
            # with open(filename, 'r') as filehandle:
            #     previousList = json.load(filehandle)
            previousList=db.get_ts(name).split(',')
            previousList = list(map(int, previousList))
        except Exception:
            previousList=[]
        print ("previous list" )

        if  not restart :
            print ("Lista append")
            lista = previousList + lista
        # with open(filename, 'w') as filehandle:
        #     json.dump(lista,filehandle)
        str_lista= ",".join(str(v) for v in lista)
        db.set_ts(name,str_lista)

    #desv_mse = 0
    print ("la lista al final es "+ str(type(lista)))
    print (lista)

    salida = ft.model_univariate(lista,num_fut,desv_mae,train,name)

    return jsonify(salida), 201


@server.route('/back_univariate', methods=['POST'])
def univariate_engine():
    db.init_database()

    if not request.json:
        abort(400)

    timedata = request.get_json()
    print (timedata)
    lista=timedata['data']

    num_fut = int(timedata.get('num_future', 5))
    desv_mae = int(timedata.get('desv_metric', 2))
    name = timedata.get('name', 'NA')
    train = timedata.get('train', True)
    restart = timedata.get('restart', False)

    print ("train?"+ str(train))
    print ("restart?" + str(restart))
    print ("Received TS")


    if(name != 'NA'):
        filename= './lst/'+name+'.lst'
        try:
            # with open(filename, 'r') as filehandle:
            #     previousList = json.load(filehandle)
            previousList=db.get_ts(name).split(',')
            previousList = list(map(int, previousList))
        except Exception:
            previousList=[]
        print ("previous list" )

        if  not restart :
            print ("Lista append")
            lista = previousList + lista
        # with open(filename, 'w') as filehandle:
        #     json.dump(lista,filehandle)
        str_lista= ",".join(str(v) for v in lista)
        db.set_ts(name,str_lista)

    #desv_mse = 0
    print ("la lista al final es "+ str(type(lista)))
    print (lista)
    print (name )

    print ("invoco el backend")
    salida = model_univariate.s(lista_datos=lista,num_fut=num_fut,desv_mse=desv_mae,train=train,name=name).apply_async()

    print (salida.id)

    #task = long_task.apply_async()
    valor = {'task_id': salida.id}
    return jsonify(valor), 200
    #return jsonify(salida), 201

@server.route('/back_univariate_status/<task_id>')
def univariate_taskstatus(task_id):
    task = model_univariate.AsyncResult(task_id)
    print ("llega aqui")
    print (task)

    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'current': 0,
            'total': 1,
            'status': 'Pending...'
        }
    elif task.state != 'FAILURE':
        response = {
            'state': task.state,
            'current': task.info.get('current', 0),
            'total': task.info.get('total', 1),
            'status': task.info.get('status', '')
        }
        if 'result' in task.info:
            response['result'] = task.info['result']
    else:
        # something went wrong in the background job
        response = {
            'state': task.state,
            'current': 1,
            'total': 1,
            'status': str(task.info),  # this is the exception raised
            'result': task.info['result']
        }
    print (task.state)
    print(task.info)
    return jsonify(response)




############################backen functions


@celery.task(bind=True)
def model_univariate(self, lista_datos,num_fut,desv_mse,train,name):
    engines_output={}
    debug = {}

    self.update_state(state='PROGRESS',
                      meta={'running': 'LSTM',
                            'status': ''})
    if not train:

        (model_name,model,params)=get_best_model('winner_'+name)
        # print ("recupero el motor " )
        winner= model_name
        if winner == 'LSTM':
            try:
                engines_output['LSTM'] = anomaly_uni_LSTM(lista_datos,num_fut,desv_mse,train,name)
                debug['LSTM'] = engines_output['LSTM']['debug']
            except Exception as e:
                print(e)
                print ('ERROR: exception executing LSTM univariate')
        elif winner == 'VAR':
            engines_output['VAR'] = univariate_forecast_VAR(lista_datos,num_fut,name)
            debug['VAR'] = engines_output['VAR']['debug']
        elif winner == 'Holtwinters':
           engines_output['Holtwinters'] = forecast_holt(lista_datos,num_fut,desv_mse,name)
           debug['Holtwinters'] = engines_output['Holtwinters']['debug']
        else:
            print ("Error")

    else:

        try:
            engines_output['LSTM'] = anomaly_uni_LSTM(lista_datos,num_fut,desv_mse,train,name)
            debug['LSTM'] = engines_output['LSTM']['debug']
        except Exception as e:
            print(e)
            print ('ERROR: exception executing LSTM univariate')
        self.update_state(state='PROGRESS',
                  meta={'running': 'LSTM',
                        'status': engines_output['LSTM']})

        #try:
            #if (len(lista_datos) > 100):
                ##new_length=
                #lista_datos_ari=lista_datos[len(lista_datos)-100:]
            #engines_output['arima'] = anomaly_AutoArima(lista_datos_ari,num_fut,len(lista_datos),desv_mse)
            #debug['arima'] = engines_output['arima']['debug']
        #except  Exception as e:
            #print(e)
            #print ('ERROR: exception executing Autoarima')

        try:
            if (train):
                engines_output['VAR'] = univariate_anomaly_VAR(lista_datos,num_fut,name)
                debug['VAR'] = engines_output['VAR']['debug']
            else:
                engines_output['VAR'] = univariate_forecast_VAR(lista_datos,num_fut,name)
                debug['VAR'] = engines_output['VAR']['debug']
        except  Exception as e:
            print(e)
            print ('ERROR: exception executing VAR')
        self.update_state(state='PROGRESS',
                  meta={'running': 'VAR',
                        'status': engines_output['VAR']})

        try:
               if (train ):
                   engines_output['Holtwinters'] = anomaly_holt(lista_datos,num_fut,desv_mse,name)
                   debug['Holtwinters'] = engines_output['Holtwinters']['debug']
               else:
                   print ("entra en forecast")
                   engines_output['Holtwinters'] = forecast_holt(lista_datos,num_fut,desv_mse,name)
                   debug['Holtwinters'] = engines_output['Holtwinters']['debug']
        except  Exception as e:
               print(e)
               print ('ERROR: exception executing Holtwinters')
        self.update_state(state='PROGRESS',
                  meta={'running': 'Holtwinters',
                        'status': engines_output['Holtwinters']})


        best_mae=999999999
        winner='VAR'
        print ('The size is: ')
        print (len(engines_output))
        for key, value in engines_output.items():
            print (key + "   " + str(value['mae']))

            if value['mae'] < best_mae:
                best_mae=value['mae']
                winner=key
            print(winner)

        new_model('winner_'+name, winner, pack('N', 365),'',0)


        print (winner)

    print ("el ganador es " + str(winner))
    print (engines_output[winner])
    temp= {}
    temp['debug']=debug
    return merge_two_dicts(engines_output[winner] , temp)




@server.route('/multivariate', methods=['POST'])
def multivariate_engine():
    if not request.json:
        abort(400)


    timedata = request.get_json()
    items = timedata['timeseries']
    name = timedata.get('name', 'NA')
    list_var=[]
    for item in items:
        data = item['data']
        if(name != 'NA'):
            sub_name = item['name']

            filename= './lst/'+name + '_' + sub_name +'.lst'
            try:
                with open(filename, 'r') as filehandle:
                    previousList = json.load(filehandle)
            except Exception:
                previousList=[]

            lista = previousList + data
            with open(filename, 'w') as filehandle:
                json.dump(lista,filehandle)


        list_var.append(data)



    lista = timedata['main']
    if(name != 'NA'):
        filename= './lst/'+name+'.lst'
        try:
            with open(filename, 'r') as filehandle:
                previousList = json.load(filehandle)
        except Exception:
            previousList=[]

        lista = previousList + lista
        with open(filename, 'w') as filehandle:
            json.dump(lista,filehandle)

    list_var.append(lista)

    num_fut = int(timedata.get('num_future', 5))
    desv_mae = int(timedata.get('desv_metric', 2))


    desv_mse = 0

    salida = ft.model_multivariate(list_var,num_fut,desv_mae)
    #print(salida)
    return jsonify(salida), 201


@server.route('/')
def index():
    return "Timecop ready to play"

if __name__ == '__main__':
    db.init_database()
    app.run(host = '0.0.0.0',port=PORT)
