import os

import numpy as np
from sklearn.model_selection import ShuffleSplit
from sklearn.neighbors import KNeighborsRegressor


def build_validation_set_prescription(all_x, all_y, all_u):
    num_prescription = len(all_x)
    train_x, valid_x = [], []
    train_y, valid_y = [], []
    train_u, valid_u = [], []

    for i in range(num_prescription):
        x, y, u = all_x[i], all_y[i], all_u[i]
        rs = ShuffleSplit(n_splits=1, test_size=.20, random_state=0)
        train_index, test_index = rs.split(x).__next__()
        X_train_all, X_test = x[train_index], x[test_index]
        y_train_all, y_test = y[train_index], y[test_index]
        u_train_all, u_test = u[train_index], u[test_index]

        train_x.append(X_train_all)
        train_y.append(np.array(y_train_all))

        valid_x.append(X_test)
        valid_y.append(np.array(y_test))

        train_u.append(u_train_all)
        valid_u.append(u_test)

    data = {
        'train_x': train_x, 'train_y': train_y, 'train_u': train_u,
        'valid_x': valid_x, 'valid_y': valid_y, 'valid_u': valid_u
    }

    return data


def get_impute_outcome(x_collection, y_collection, impute_dict):
    """
    return imputation for a set of data
    :param x_collection: list of data, each of which is prescribe with one combination of prescription
    :param y_collection: list of outcome, each of which is prescribe with one combination of prescription
    :param impute_dict: transformer and pho for kNN
    :return:
    """
    # get imputation model
    num_prescription = len(y_collection)

    all_x = np.concatenate(x_collection, axis=0)
    all_y = np.concatenate(y_collection, axis=0)

    prescription = [i * np.ones(len(y_collection[i])) for i in range(num_prescription)]
    all_z = np.concatenate(prescription, axis=0)
    all_z = np.array(all_z, dtype=int)

    outcome = []

    for pres_id in range(num_prescription):
        x = x_collection[pres_id]
        y = y_collection[pres_id]

        num_sample = len(x)
        n_neighbor = int(impute_dict['rho'] * int(np.sqrt(num_sample)))
        transformer = impute_dict['transformer'][pres_id]

        x = transformer.transform(x)
        knn_model = KNeighborsRegressor(n_neighbors=n_neighbor)
        knn_model.fit(x, y)

        all_x_trans = transformer.transform(all_x)
        outcome.append(knn_model.predict(all_x_trans))

    outcome = np.array(outcome).T
    for i in range(len(all_z)):
        outcome[i, all_z[i]] = all_y[i]

    return all_x, outcome


def return_prediction_and_std(input_data, model_collections):
    """
    predict outcome with 100 sub-models
    :param input_data: input data
    :param model_collections: a dict of core model and sub models
    :return: prediction outcome and its std
    """
    num_prescription = len(model_collections['core_model'])

    prediction_outcome = []
    prediction_std = []

    for pres_id in range(num_prescription):
        # get core model
        prediction_outcome.append(
            model_collections['core_model'][pres_id].predict(input_data))

        # find std
        submodel_outcomes = []
        for model in model_collections['submodels'][pres_id]:
            submodel_outcomes.append(model.predict(input_data))

        submodel_outcomes = np.std(submodel_outcomes, axis=0)
        prediction_std.append(submodel_outcomes)

    return np.array(prediction_outcome).T, np.array(prediction_std).T


def get_boltzman_policy(y_predict, epsilon):
    """
    return the probability of the random prescription
    :param y_predict: outcome for each type of prescription
    :param epsilon: soften factor
    :return:
    """
    norm_y = y_predict - np.min(y_predict, axis=1, keepdims=True)
    p = np.exp(-epsilon * norm_y)
    return p / np.sum(p, axis=1, keepdims=True)


def eval_prescription_probability(probability, impute_outcome):
    """
    get randomized prescription outcome
    :param probability: probability of choosing each type of prescription
    :param impute_outcome: impute outcome
    :return: outcome
    """
    prescription_outcome = np.zeros(len(probability))
    num_prescription = np.shape(probability)[1]

    for p in range(num_prescription):
        prescription_outcome += np.array([item[p] * k for item, k in zip(impute_outcome, probability[:, p])])

    return prescription_outcome


def find_prescription_threshold(pred_y, pred_y_std, previous):
    """
    find threshold of for changing the prescription or not
    :param pred_y: predicted outcome of the prescription
    :param pred_y_std: prediction std
    :param previous: previous bp or a1c
    :return: thresholds that change the prescription or not
    """
    num_sample = len(pred_y)
    threshold = np.sqrt(-2 * np.log(0.1 / num_sample))

    T = previous - np.min(pred_y + threshold * pred_y_std, axis=1)
    T = np.maximum(T, 0)

    std_t = np.min(pred_y, axis=-1) < (previous - T)
    return std_t


def get_base_path():
    '''
    Determine the environment I run the code
    :return: base directory
    '''
    home = os.path.expanduser("~")
    if home == '/home/yannisplab':
        return os.path.join(home, 'henghuiz')
    else:
        return os.path.join(home, 'remote')
