import os 
import pandas as pd 
import numpy as np 
from scipy.stats import entropy
from scipy.special import binom
import math
import sys
import time
import argparse
# local modules
from utils import check_volume

def parse_arguments():
    """
    parse and check the command-line arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("datafile", type=argparse.FileType('r'), help="csv input data set")
    parser.add_argument("-v","--verbose", help="increase output verbosity",action="store_true")
    parser.add_argument("-m","--max_binom", type=int, default = 1000000, help="maximum number of mappings per N")
    parser.add_argument("output", type=argparse.FileType('w'), help="output data set")
    args = parser.parse_args()
    # checks
    print("input filename", args.datafile)
    print("output filename", args.output)
    if args.verbose:
        print("verbosity turned on")
    if args.max_binom < 1:
        raise Exception("max_binom must be positive")
    return args

def compute_entropies(at_clust,df,mapping,pr,V):
    """
    resolution, relevance, and mapping entropy starting from original and atomistic data frames
    """
    # coarse-grained clustering
    cg_clust = df.groupby(df.columns[mapping].tolist()).size().reset_index().rename(columns={0:'records'})
    cg_clust.columns = pd.concat([pd.Series(df.columns[mapping]), pd.Series("records")])
    # resolution with respect to the full sampling
    hs = entropy(cg_clust["records"])
    #print("hs for %s = %8.6lf" % (str(mapping),hs))
    ks = np.unique(cg_clust["records"], return_counts=True)
    pk = np.multiply(ks[0], ks[1])
    hk = entropy(pk)
    #print("hk for %s = %8.6lf" % (str(mapping),hk))
    # multiplicity of hr microstates mapping onto each
    omega_1 = at_clust.groupby(at_clust.columns[mapping].tolist()).size().reset_index().rename(columns={0:'records'})
    #print("omega_1", omega_1)
    # smeared probability distribution
    p_bar_r = cg_clust["records"]/df.shape[0]/omega_1["records"]
    new_p_bar = pd.concat([omega_1,p_bar_r],axis=1) # to keep track of all the cg configurations
    # state-wise mapping entropy
    mapping_entropy = []
    for n in range(at_clust.shape[0]):
        s = np.where((at_clust.iloc[n,mapping] == new_p_bar.iloc[:,:-2]).all(1) == True)[0][0]
        mapping_entropy.append(pr[n]*np.log(pr[n]/new_p_bar.iloc[s,-1]))
    tot_smap = sum(mapping_entropy)
    #print("smap for %s = %8.6lf" % (str(mapping),tot_smap))
    delta_s_conf = (len(at_clust.columns) - 1 - len(mapping))*np.log(V) - entropy(at_clust["records"]) + hs
    #print("infinite sampling mapping entropy for %s = %8.6lf" % (str(mapping),delta_s_conf))
    return len(mapping),mapping,list(at_clust.columns[mapping]),hs,hk,tot_smap,delta_s_conf

def main():
    """
    main function
    """
    start_time = time.time()

    args = parse_arguments()

    # read_data
    with args.datafile as f:
        ncols = len(f.readline().split(','))
    print("number of columns in the dataset = ", ncols)
    df = pd.read_csv(args.datafile.name, sep = ",",usecols=range(1,ncols))
    print("df shape", df.shape)
    print("df.columns", df.columns)
    n_at = df.shape[1]
    
    # atomistic clustering: the original dataframe is divided in microstates
    at_clust = df.groupby(df.columns.tolist()).size().reset_index().rename(columns={0:'records'})
    print("at_clust", at_clust)
    print("atomistic columns", at_clust.columns)
    print("at_clust shape", at_clust.shape)
    pr = at_clust["records"]/df.shape[0] # detailed, atomistic probability distribution
    # check volume
    V = check_volume(df,ncols)
    
    # creating fully detailed mapping
    print("total number of mappings = ", math.pow(2,n_at) - 1)
    at_mapping = np.array(range(n_at))
    print("df.columns[at_mapping]",df.columns[at_mapping])
    print("at_clust.columns[at_mapping]",at_clust.columns[at_mapping])
    print("atomistic resolution ", entropy(at_clust["records"])) # computing fully atomistic resolution
    
    cg_mappings = dict()
    # going through the levels of coarse-graining
    for ncg in range(1,n_at+1):
        print("ncg = ", ncg, ", elapsed time (seconds) = %8.6lf" % (time.time() - start_time))
        cg_count = int(binom(n_at,ncg))
        print("cg_count", cg_count)
        k = 0
        max_range = min(cg_count,args.max_binom)
        while k < max_range:
            mapping = np.random.choice(at_mapping, ncg, replace=False)
            mapping.sort()
            key = tuple(mapping)
            if key not in cg_mappings.keys():
                k += 1
                if args.verbose:
                    print("adding key", key, " k = ", k)
                cg_mappings[key] = compute_entropies(at_clust, df, mapping, pr, V)
    
    output_df = pd.DataFrame(cg_mappings.values())
    output_df.columns = ["N","mapping","trans_mapping","hs","hk","smap","smap_inf"]
    output_df.to_csv(args.output,sep=",",float_format = "%8.6lf")
    
    print("Total execution time (seconds) %8.6lf" % (time.time() - start_time))

# running main
main()