from typing import *
import pandas as pd
import os
import pickle
import json

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.svm import SVC


from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import make_pipeline
from sklearn.exceptions import NotFittedError

from flask import Flask, jsonify, abort
from flask_restx import Api, Resource
from flask_restful import reqparse
from werkzeug.datastructures import FileStorage


app = Flask(__name__)
api = Api(app)

upload_parser = api.parser()
upload_parser.add_argument('file', location='files',
                           type=FileStorage, required=True)
                           
upload_parser.add_argument('experiment_id',
                           type=str, default="0")
                           
upload_parser.add_argument('model_name', type=str, default="SVC")
                           
upload_parser.add_argument('path_to_model_params', type=str,
                            required=False, default = 'models_params/SVC_params.json')

feature_columns = ['Age', 'Embarked', 'Pclass', 'Sex']
target_column = 'Survived'
all_columns = feature_columns + [target_column]



models = {

    "SVC": {
        "file_with_params": "models_params/SVC_params.json",
        "tutorial": "https://scikit-learn.org/stable/modules/generated/sklearn.svm.SVC.html"
    },
    
    "GradientBoostingClassifier": {
        "file_with_params": "models_params/GradientBoostingClassifier_params.json",
         "tutorial": "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.GradientBoostingClassifier.html"
    },
     
    "LogisticRegression": {
        "file_with_params": "models_params/LogisticRegression_params.json",
         "tutorial": "https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html"
    },
}

# Удаляем NaN-ы из данных
def prepare_data(df, for_train=True):
    if for_train:
        columns = ['Age', 'Embarked', 'Pclass', 'Sex', 'Survived']
        df = df[columns].dropna()
        return df
    else:
        columns = ['Age', 'Embarked', 'Pclass', 'Sex']
        df = df[columns].dropna()
        return df
        
        
@api.route('/train', methods=['PUT'], doc={'description': 'Запустить обучение выбранной модели на датасете Titanic'})
@api.expect(upload_parser)
class Train(Resource):
    @api.doc(params={'file': f'Файл в формате CSV с полями Age, Embarked, Pclass, Sex, Survived'})
    @api.doc(params={'experiment_id': f'Номер эксперимента'})
    @api.doc(params={'path_to_model_params': f'Путь к файлу с параметрами выбранной модели'})
    
    @api.doc(responses={403: 'Id модели не найден!'})
    @api.doc(responses={200: 'Обучение прошло успешно!'})
    @api.doc(responses={202: 'Модель обучена, но такой эксперимент уже существует!'})
    def put(self):
    
        args = upload_parser.parse_args()
        # Загрузка модели по её параметрам
        base_model = self.load_model(args.path_to_model_params)
        # Пайплайн с преобразованием данных
        model = make_pipeline(
            ColumnTransformer([
                ('ohe', OneHotEncoder(), ['Pclass', 'Embarked']),
                ('binarizer', OrdinalEncoder(), ['Sex'])
                ],
                remainder='passthrough'),
            base_model
        )
        # Чтение данных и предобработка
        data = pd.read_csv(args.file)
        X, y = prepare_data(data)
        # Фит модели и сохранение
        model.fit(X, y)
        # Сохранение результата
        save_filename = "train_results/" + args.path_to_model_params[args.path_to_model_params.find('/')+1:args.path_to_model_params.rfind('_')] + "_" + args.experiment_id + ".pkl"
        os.makedirs(os.path.dirname(save_filename), exist_ok=True)
        # Смотрим, проводилось ли ранее обучение по заданному номеру эксперимента
        if os.path.isfile(save_filename):
            pickle.dump(model, open(save_filename, 'wb'))
            return 'Модель обучена, но такой эксперимент уже существует!', 202
        else:
            pickle.dump(model, open(save_filename, 'wb'))
            return 'Обучение прошло успешно!', 200

        
    @staticmethod
    def load_model(model_path):
        # Загружаю данные с параметрами модели
        full_model_params_path = os.getcwd() + '/' + model_path
        with open(full_model_params_path, 'r') as JSON:
            model_params = json.load(JSON)
        # Загружаю модель с параметрами, исходя из названия
        if 'SVC' in model_path:
            return SVC(**model_params)
        elif 'GradientBoostingClassifier' in model_path:
            return GradientBoostingClassifier(**model_params)
        elif 'LogisticRegression' in model_path:
            return LogisticRegression(**model_params)
        else:
            api.abort(403, message = "Модель с такими параметрами не определена!")
    
        
        
@api.route('/models', methods=['GET', 'DELETE'])
class GetModels(Resource):
    def get(self):
        return jsonify(models)
    @api.doc(params={'experiment_id': f'Номер эксперимента для удаления'})
    @api.doc(params={'model_name': f'Название модели'})
    def delete(self):
        print('deleted')
        


@api.route('/predict', methods=['POST'])
@api.expect(upload_parser)
class Predict(Resource):
    @api.doc(params={'file': f'Файл в формате CSV с полями Age, Embarked, Pclass, Sex'})
    @api.doc(params={'experiment_id': f'Номер эксперимента'})
    @api.doc(params={'model_name': f'Название модели'})
    def post(self):
        args = upload_parser.parse_args()
        # Загрузка и предобработка данных
        data = pd.read_csv(args.file)
        X = data[feature_columns]
        X = prepare_data(X, for_train=False)
        # Загрузка модели
        model = pickle.load(open('train_results/' + args.model_name + "_" + str(args.experiment_id) + '.pkl', 'rb'))
        # Предсказания
        preds = model.predict(X)
        return {'Предсказания модели': preds.tolist()}, 200


#@api.route('/models', methods=[])
#class DeleteModel(Resource):
#    @api.doc(params={'experiment_id': f'Номер эксперимента для удаления'})
#    @api.doc(params={'model_name': f'Название модели'})
#    def delete(self):
#        print('a')
        

if __name__ == '__main__':
    app.run(debug=True)



        
