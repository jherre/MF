
"""
    ########################################################
    Gene_func_prediction (``examples.gene_func_prediction``)
    ########################################################
    
    .. note:: This example is in progress.
    
    As a background reading before this example, we suggest reading [Schietgat2010]_ and [Schachtner2008]_ .
        
    This example from functional genomics deals with gene function prediction. Two main characteristics of function 
    prediction task are:
    
        #. single gene can have multiple functions, 
        #. the functions are organized in a hierarchy, in particular in a hierarchy structered as a rooted tree -- MIPS's
           FunCat. In example is used data set that originates from S. cerevisiae and has annotations from the MIPS Functional
           Catalogue. A gene related to some function is automatically related to all its ancestor functions.
    
    These characteristics describe hierarchical multi-label classification (HMC) setting. 
    
    Here is the outline of this gene function prediction task. 
    
        #. Dataset Preprocessing.
        #. Gene selection
        #. Feature generation. 
        #. Feature selection
        #. Classification of the mixture matrix and comply with the hierarchy constraint. 
    
    To run the example simply type::
        
        python gene_func_prediction.py
        
    or call the module's function::
    
        import mf.examples
        mf.examples.gene_func_prediction.run()
        
    .. note:: This example uses matplotlib library for producing visual interpretation.
"""

import mf
import numpy as np
import scipy.sparse as sp
from os.path import dirname, abspath, sep

try:
    import matplotlib.pylab as plb
except ImportError, exc:
    raise SystemExit("Matplotlib must be installed to run this example.")
    

def run():
    """
    Run the gene function prediction example on the S. cerevisiae sequence data set (D1 FC seq).
    
    The methodology is as follows:
        #. Reading S. cerevisiae sequence data, i. e. train, validation and test set. Reading meta data,  
           attributes' labels and class labels.
        #. Preprocessing, i. e. normalizing data matrix of test data and data matrix of joined train and validation
           data. 
        #. Factorization of train data matrix. 
        #. Factorization of test data matrix.  
        #. Application of rules for class assignments. Two rules are used, average correlation and maximal 
           correlation, as in [Schachtner2008]_ .
    """
    # reading data set, attributes' labels and class labels 
    tv_data, test_data, idx2attr, idx2class = read()
    # normalization of train data set
    tv_data = preprocess(tv_data)
    # normalization of test data set
    test_data = preprocess(test_data)
    # factorization of train data matrix
    tv_data = factorize(tv_data)
    # factorization of test data matrix
    test_data = factorize(test_data)
    # correlation computation 
    corrs = compute_correlations(tv_data, test_data)
    # class assignments
    labels = assign_labels(corrs, tv_data, idx2class)
    # precision and recall measurements
    plot(labels, test_data, idx2class)    
    
def read():
    """
    Read S. cerevisiae FunCat annotated sequence data set (D1 FC seq).
    
    Return attributes' values and class information of the test data set and joined train and validation data set. Additional mapping functions 
    are returned mapping attributes' names and classes' names to indices. 
    """
    print "Reading S. cerevisiae FunCat annotated sequence data set (D1 FC seq) ..."
    dir = dirname(dirname(abspath(__file__))) + sep + 'datasets' + sep + 'S_cerevisiae_FC' + sep + 'seq_yeast_FUN' + sep
    train_data = dir + 'seq_yeast_FUN.train.arff'
    valid_data = dir + 'seq_yeast_FUN.valid.arff'
    test_data = dir + 'seq_yeast_FUN.test.arff'
    print " Reading S. cerevisiae FunCat annotated sequence (D1 FC seq) TRAIN set ..."
    train, idx2attr, idx2class = transform_data(train_data, include_meta = True)
    print " ... Finished."  
    print " Reading S. cerevisiae FunCat annotated sequence (D1 FC seq) VALIDATION set ..."
    valid = transform_data(valid_data)
    print " ... Finished."  
    print " Reading S. cerevisiae FunCat annotated sequence (D1 FC seq) TEST set ..."
    test = transform_data(test_data)
    print " ... Finished."
    print " Joining S. cerevisiae FunCat annotated sequence (D1 FC seq) TEST and VALIDATION set ..."
    tv_data = _join(train, valid)
    print " ... Finished."    
    print "... Finished"
    return tv_data, test, idx2attr, idx2class

def transform_data(path, include_meta = False):
    """
    Read data in the ARFF format and transform it to suitable matrix for factorization process. For each feature update direct and indirect 
    class information exploiting properties of Functional Catalogue hierarchy. 
    
    Return attributes' values and class information. If :param:`include_meta` is specified additional mapping functions are provided with 
    mapping from indices to attributes' names and indices to classes' names.  
    
    :param path: Path of directory with sequence data set (D1 FC seq).
    :type path: `str`
    :param include_meta: Specify if the header of the ARFF file should be skipped. The header of the ARFF file 
                               contains the name of the relation, a list of the attributes and their types. Default
                               value is False.  
    :type include_meta: `bool`
    """
    class2idx = {}
    attr2idx = {}
    
    idx_attr = 0
    idx_class = 0
    idx = 0
    feature = 0
    used_idx = set()
    section = 'h'

    for line in open(path):
        if section == 'h': 
            tokens = line.strip().split()
            line_type = tokens[0] if tokens else None
            if line_type == "@ATTRIBUTE":
                if tokens[2] in ["numeric"]:
                    attr2idx[tokens[1]] = idx_attr
                    idx_attr += 1
                    used_idx.add(idx)
                if tokens[1] in ["class"] and tokens[2] in ["hierarchical", "classes"]:
                    class2idx = _reverse(dict(list(enumerate((tokens[3] if tokens[3] != '%' else tokens[5]).split(",")))))
                    idx_class = idx
                idx += 1
            if line_type == "@DATA":
                section = 'd'
                idxs = set(xrange(idx)).intersection(used_idx)
                attr_data = np.mat(np.zeros((1e4, len(attr2idx))))
                class_data = np.mat(np.zeros((1e4, len(class2idx))))
        elif section == 'd':
            d, _, comment = line.strip().partition("%")
            values = d.split(",")
            # update class information for current feature
            class_var = map(str.strip, values[idx_class].split("@"))
            for cl in class_var:
                # update direct class information
                class_data[feature, class2idx[cl]] += 4.
                # update indirect class information through FunCat hierarchy
                cl_a = cl.split("/")
                cl = "/".join(cl_a[:3] + ['0'])
                if cl in class2idx:
                    class_data[feature, class2idx[cl]] += 3.
                cl = "/".join(cl_a[:2] + ['0', '0'])
                if cl in class2idx:
                    class_data[feature, class2idx[cl]] += 2.
                cl = "/".join(cl_a[:1] + ['0', '0', '0'])
                if cl in class2idx:
                    class_data[feature, class2idx[cl]] += 1.
            # update attribute values information for current feature 
            i = 0 
            for idx in idxs:
                attr_data[feature, i] = abs(float(values[idx] if values[idx] != '?' else 0.))
                i += 1
            feature += 1
    return ({'feat': feature, 'attr': attr_data, 'class': class_data}, _reverse(attr2idx), _reverse(class2idx)) if include_meta else {'feat': feature, 'attr': attr_data[:feature, :], 'class': class_data}

def _join(train, valid):
    """
    Join test and validation data of the S. cerevisiae FunCat annotated sequence data set (D1 FC seq). 
    
    Return joined test and validation attributes' values and class information.
     
    :param train: Attributes' values and class information of the train data set. 
    :type train: `numpy.matrix`
    :param valid: Attributes' values and class information of the validation data set.
    :type valid: `numpy.matrix`
    """
    n_train =  train['feat']
    n_valid =  valid['feat']
    return {'feat': n_train + n_valid, 
            'attr': np.vstack((train['attr'][:n_train, :], valid['attr'][:n_valid, :])),
            'class': np.vstack((train['class'][:n_train, :], valid['class'][:n_valid, :]))}

def _reverse(object2idx):
    """
    Reverse 1-to-1 mapping function.
    
    Return reversed mapping.
    
    :param object2idx: Mapping of objects to indices or vice verse.
    :type object2idx: `dict`
    :rtype: `dict`
    """
    return dict(zip(object2idx.values(), object2idx.keys()))

def preprocess(data):
    """
    Preprocess S.cerevisiae FunCat annotated sequence data set (D1 FC seq). Preprocessing step includes data 
    normalization.
    
    Return preprocessed data. 
    
    :param data: Transformed data set containing attributes' values, class information and possibly additional meta information.  
    :type data: `tuple`
    """
    print "Preprocessing data matrix ..."
    data['attr'] = (data['attr'] - data['attr'].min() + np.finfo(data['attr'].dtype).eps) / (data['attr'].max() - data['attr'].min())
    print "... Finished."
    return data

def factorize(data):
    """
    Perform factorization on S. cerevisiae FunCat annotated sequence data set (D1 FC seq).
    
    Return factorized data, this is matrix factors as result of factorization (basis and mixture matrix). 
    
    :param data: Transformed data set containing attributes' values, class information and possibly additional meta information.  
    :type data: `tuple`
    """
    V = data['attr']
    model = mf.mf(V, 
                  seed = "random_vcol", 
                  rank = 40, 
                  method = "nmf", 
                  max_iter = 75, 
                  initialize_only = True,
                  update = 'divergence',
                  objective = 'div')
    print "Performing %s %s %d factorization ..." % (model, model.seed, model.rank) 
    fit = mf.mf_run(model)
    print "... Finished"
    sparse_w, sparse_h = fit.fit.sparseness()
    print """Stats:
            - iterations: %d
            - KL Divergence: %5.3f
            - Euclidean distance: %5.3f
            - Sparseness basis: %5.3f, mixture: %5.3f""" % (fit.fit.n_iter, fit.distance(), fit.distance(metric = 'euclidean'), sparse_w, sparse_h)
    data['W'] = fit.basis()
    data['H'] = fit.coef()
    return data
    
def compute_correlations(train, test):
    """
    Estimate correlation coefficients between profiles of train basis matrix and profiles of test basis matrix. 
    
    Return the estimated correlation coefficients of the features (variables).  
    
    :param train: Factorization matrix factors of train data set. 
    :type train: `dict`
    :param test: Factorization matrix factors of test data set. 
    :type test: `dict`
    :rtype: `numpy.matrix`
    """
    print "Estimating correlation coefficients ..."
    corrs = np.corrcoef(train['W'], test['W'])
    # alternative, it is time consuming - can be used for partial evaluation
    """corrs = {}
    for i in xrange(test['W'].shape[0]):
        corrs.setdefault(i, np.mat(np.zeros((train['W'].shape[0], 1))))
        for j in xrange(train['W'].shape[0]):
            corrs[i][j, 0] = _corr(test['W'][i, :], train['W'][j, :])"""
    print "... Finished."
    return corrs

def _corr(x, y):
    """
    Compute Pearson's correlation coefficient of x and y. Numerically stable algebraically equivalent equation for 
    coefficient computation is used. 
    
    Return correlation coefficient between x and y which is by definition in [-1, 1].
    
    :param x: Random variable.
    :type x: `numpy.matrix`
    :param y: Random variable.
    :type y: `numpy.matrix`
    :rtype: `float`
    """
    n1 = x.size - 1
    xm = x.mean()
    ym = y.mean()
    sx = x.std(ddof = 1)
    sy = y.std(ddof = 1)
    return 1. / n1 * np.multiply((x - xm) / sx, (y - ym) / sy).sum()

def assign_labels(corrs, train, idx2class, method = 0.001):
    """
    Apply rules for class assignments. In [Schachtner2008]_ two rules are proposed, average correlation and maximal 
    correlation. Here, the average correlation rule is used. These rules are generalized to multi-label 
    classification incorporating hierarchy constraints. 
    
    User can specify the usage of one of the following rules:
        #. average correlation,
        #. maximal correlation,
        #. threshold average correlation.
    
    Though any method based on similarity measures can be used, we estimate correlation coefficients. Let w be the
    gene profile of test basis matrix for which we want to predict gene functions. For each class C a separate 
    index set A of indices is created, where A encompasses all indices m, for which m-th profile of train basis 
    matrix has label C. Index set B contains all remaining indices. Now, the average correlation coefficient between w
    and elements of A is computed, similarly average correlation coefficient between w and elements of B. Finally, 
    w is assigned label C if the former correlation over the respective index set is greater than the 
    latter correlation.
    
    .. note: Described rule assigns the class label according to an average correlation of test vector with all
             vectors belonging to one or the other index set. Minor modification of this rule is to assign the class
             label according to the maximal correlation occurring between the test vector and the members of each
             index set. 
             
    .. note: As noted before the main problem of this example is the HMC (hierarchical multi-label classification) 
             setting. Therefore we generalized the concepts from articles describing the use of factorization
             for binary classification problems to multi-label classification. Additionally, we use the weights
             for class memberships to incorporate hierarchical structure of MIPS MIPS Functional
             Catalogue.
    
    Return mapping of genes to their predicted gene functions. 
    
    :param corrs: Estimated correlation coefficients between profiles of train basis matrix and profiles of test 
                  basis matrix. 
    :type corrs: `dict`
    :param train: Class information of train data set. 
    :type train: `dict`
    :param idx2class: Mapping between classes' indices and classes' labels. 
    :type idx2class: `dict`
    :param method: Type of rule for class assignments. Possible are average correlation, maximal correlation by 
                   specifying ``average`` or ``maximal`` respectively. In addition threshold average correlation is
                   supported. If threshold rule is desired, threshold is specified instead. By default 
                   threshold rule is applied. 
    :type method: `float` or `str`
    :rtype: `dict`
    """
    print "Assigning class labels ..."
    labels = {}
    n_train = train['feat']
    key = 0
    for test_idx in xrange(n_train, corrs.shape[0]):
        labels.setdefault(key, [])
        for cl_idx in idx2class:
            if method == "average":
                count = (train['class'][:, cl_idx] != 0).sum()
                if count == 0:
                    continue
                # weighted summation of correlations over respective index sets
                avg_corr_A = np.dot(corrs[:n_train, test_idx], train['class'][:, cl_idx]) / count
                avg_corr_B = np.dot(corrs[:n_train, test_idx], train['class'][:, cl_idx] != 0) / (n_train - count)
                if (avg_corr_A > avg_corr_B):
                   labels[key].append(cl_idx) 
            elif method == "maximal": 
                max_corr_A = np.multiply(corrs[:n_train, test_idx], train['class'][:, cl_idx]).max()
                max_corr_B = np.multiply(corrs[:n_train, test_idx], train['class'][:, cl_idx] != 0).max()
                if (max_corr_A > max_corr_B):
                   labels[key].append(cl_idx) 
            elif isinstance(method, float):
                count = (train['class'][:, cl_idx] != 0).sum()
                if count == 0:
                    continue
                # weighted summation of correlations over respective index set
                avg_corr = np.dot(corrs[:n_train, test_idx], train['class'][:, cl_idx]) / count
                if (avg_corr >= method):
                    labels[key].append(cl_idx)
            else:
                raise ValueError("Unrecognized class assignment rule.")
        key += 1
        if key % 100 == 0:
            print " %d/%d" % (key, corrs.shape[0] - n_train)
    print "... Finished."
    print labels
    return labels

def plot(labels, test, idx2class):
    """
    Report the performance with the precision-recall (PR) based evaluation measures. 
    
    Beside PR also ROC based evaluations have been used before to evaluate gene function prediction approaches. PR
    based better suits the characteristics of the common HMC task, in which many classes are infrequent with a small
    number of genes having particular function. That is for most classes the number of negative instances exceeds
    the number of positive instances. Therefore it is sometimes preferred to recognize the positive instances instead
    of correctly predicting the negative ones (i. e. gene does not have a particular function). That means that ROC
    curve might be less suited for the task as they reward a learner if it correctly predicts negative instances. 
    
    Return PR evaluations measures
    
    :param labels: Mapping of genes to their predicted gene functions. 
    :type labels: `dict`
    :param test: Class information of test data set. 
    :type test: `dict`
    :param idx2class: Mapping between classes' indices and classes' labels. 
    :type idx2class: `dict`
    :rtype: `tuple`
    """
    avg_precision = 0. 
    avg_recall = 0.
    print "Average precision: %5.3f" % avg_precision
    print "Average recall: %5.3f" % avg_recall
    return avg_precision, avg_recall

if __name__ == "__main__": 
    """Run the gene function prediction example."""
    run()
