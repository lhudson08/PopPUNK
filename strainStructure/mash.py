'''Mash functions for database construction'''

# universal
import os
import sys
import subprocess
# additional
import collections
import pickle
from multiprocessing import Pool, Lock
from functools import partial
import numpy as np
import networkx as nx
from scipy import optimize

#####################
# Get database name #
#####################

def getDatabaseName(prefix, k):
    return prefix + "/" + prefix + "." + k + ".msh"

#############################
# create database directory #
#############################

def createDatabaseDir(outPrefix):
    outputDir = os.getcwd() + "/" + outPrefix
    # check for writing
    if not os.path.isdir(outputDir):
        try:
            os.makedirs(outputDir)
        except:
            sys.stderr.write("Cannot create output directory\n")
            sys.exit(1)

#####################################
# Store distance matrix in a pickle #
#####################################

def storePickle(rlist, qlist, X, qindices, rindices, pklName):
    with open(pklName, 'wb') as pickle_file:
        pickle.dump([rlist, qlist, X, qindices, rindices], pickle_file)

####################################
# Load distance matrix from pickle #
####################################

def readPickle(pklName):
    with open(pklName, 'rb') as pickle_file:
        rlist, qlist, X, qindices, rindices = pickle.load(pickle_file)
    return rlist, qlist, X, qindices, rindices

#########################
# Print output of query #  # needs work still
#########################

def assignQueriesToClusters(links, G, databaseName, outPrefix):

    # open output file
    outFileName = outPrefix + "_clusterAssignment.out"
    with open(outFileName, 'w') as oFile:
        oFile.write("Query,Cluster\n")

        # parse existing clusters into existingCluster dict
        # also record the current maximum cluster number for adding new clusters
        maxCluster = 0;
        existingCluster = {}
        dbClusterFileName = "./" + databaseName + "/" + databaseName + "_clusters.csv"
        with open(dbClusterFileName, 'r') as cFile:
            for line in cFile:
                clusterVals = line.rstrip().split(",")
                if clusterVals[0] != "Taxon":
                    # account for decimal clusters that have been merged
                    intCluster = int(clusterVals[1].split('.')[0])
                    #            existingCluster[clusterVals[0]] = clusterVals[1]
                    existingCluster[clusterVals[0]] = intCluster
                    if intCluster > maxCluster:
                        maxCluster = intCluster

        # calculate query clusters here
        queryCluster = {}
        queriesInCluster = {}
        clusters = sorted(nx.connected_components(G), key=len, reverse=True)
        cl_id = maxCluster + 1
        for cl_id, cluster in enumerate(clusters):
            queriesInCluster[cl_id] = []
            for cluster_member in cluster:
                queryCluster[cluster_member] = cl_id
                queriesInCluster[cl_id].append(cluster_member)
            if cl_id > maxCluster:
                maxCluster = cl_id

        # iterate through links, which comprise both query-ref links
        # and query-query links
        translateClusters = {}
        additionalClusters = {}
        existingHits = {}
        for query in links:
            existingHits[query] = {}
            oFile.write(query + ",")
            newHits = []

            # populate existingHits dict with links to already-clustered reference sequences
            for link in links[query]:
                if link in existingCluster:
                    existingHits[query][existingCluster[link]] = 1

            # if no links to existing clusters found in the existingHits dict
            # then look at whether there are links to other queries, and whether
            # they have already been clustered
            if len(existingHits[query].keys()) == 0:

                # initialise the new cluster
                newCluster = None

                # check if any of the other queries in the same query cluster
                # match an existing cluster - if so, assign to existing cluster
                # as a transitive property
                if query in queryCluster:
                    for similarQuery in queriesInCluster[queryCluster[query]]:
                        if len(existingHits[similarQuery].keys()) > 0:
                            if newCluster is None:
                                newCluster = str(';'.join(str(v) for v in existingHits[similarQuery].keys()))
                            else:
                                newCluster = newCluster + ';' + str(';'.join(str(v) for v in existingHits[similarQuery].keys()))

                # if no similar queries match a reference sequence
                if newCluster is None:
                    if query in queryCluster:
                        # matches a query that has already been assigned a new cluster
                        if queryCluster[query] in translateClusters:
                            newCluster = translateClusters[queryCluster[query]]
                        # otherwise define a new cluster, incrementing from the previous maximum number
                        else:
                            newCluster = queryCluster[query]
                            translateClusters[queryCluster[query]] = queryCluster[query]
                        additionalClusters[query] = newCluster
                    else:
                        maxCluster += 1
                        newCluster = maxCluster

                oFile.write(str(newCluster) + '\n')

            # if multiple links to existing clusters found in the existingHits dict
            # then the clusters will have to be merged if the database is updated
            # for the moment, they can be recorded as just matching two clusters
            else:
                # matching multiple existing clusters that will need to be merged
                if len(existingHits[query].keys()) > 1:
                    hitString = str(';'.join(str(v) for v in existingHits[query].keys()))
                # matching only one cluster
                else:
                    hitString = str(list(existingHits[query])[0])
                oFile.write(hitString + "\n")

    # returns:
    # existingHits: dict of dicts listing hits to references already in the database
    # additionalClusters: dict of query assignments to new clusters, if they do not match existing references
    return additionalClusters, existingHits

##########################################
# Get sketch size from existing database #
##########################################

def getSketchSize(dbPrefix, klist, mash_exec = 'mash'):

    # identify sketch lengths used to generate databases
    sketchdb = {}
    sketch = 0
    oldSketch = 0

    # iterate over kmer lengths
    for k in klist:
        dbname = "./" + dbPrefix + "/" + dbPrefix + "." + str(k) + ".msh"
        try:
            mash_info = subprocess.Popen(mash_exec + " info -t " + dbname, shell=True, stdout=subprocess.PIPE)
            for line in iter(mash_info.stdout.readline, ''):
                line = line.rstrip().decode()
                if (line.startswith("#") is False):
                    sketchValues = line.split("\t")
                    if len(sketchValues[0]) > 0:
                        if oldSketch == 0:
                            oldSketch = int(sketchValues[1])
                        else:
                            oldSketch = sketch
                        sketch = int(sketchValues[1])
                        if (sketch == oldSketch):
                            sketchdb[k] = sketch
                        else:
                            sys.stderr.write("Problem with database; sketch size for kmer length "+str(k)+" is "+str(oldSketch)+", but smaller kmers have sketch sizes of "+str(sketch)+"\n")
                            sys.exit(1)

                        break

            # Make sure process executed correctly
            mash_info.wait()
            if mash_info.returncode != 0:
                raise RuntimeError('mash info failed')
        except subprocess.CalledProcessError as e:
            sys.stderr.write("Could not get info about " + dbname + "; command "+mash_exec + " info -t " + dbname+" returned "+str(mash_info.returncode)+": "+e.message+"\n")
            sys.exit(1)

    return sketchdb

########################
# construct a database #
########################

# Multithread wrapper around sketch
def constructDatabase(assemblyList, klist, sketch, oPrefix, threads = 1, mash_exec = 'mash'):

    # create kmer databases
    l = Lock()
    pool = Pool(processes=threads, initializer=init_lock, initargs=(l,))
    pool.map(partial(runSketch,assemblyList=assemblyList, sketch=sketch, oPrefix=oPrefix, mash_exec=mash_exec), klist)
    pool.close()
    pool.join()

# lock on stderr
def init_lock(l):
    global lock
    lock = l

# create kmer databases
def runSketch(k, assemblyList, sketch, oPrefix, mash_exec = 'mash'):
    lock.acquire()
    sys.stderr.write("Creating mash database for k = " + str(k) + "\n")
    lock.release()

    dbname = "./" + oPrefix + "/" + oPrefix + "." + str(k)
    if not os.path.isfile(dbname + ".msh"):
        mash_cmd = mash_exec + " sketch -w 1 -s " + str(sketch[k]) + " -o " + dbname + " -k " + str(k) + " -l " + assemblyList + " 2> /dev/null"
        subprocess.run(mash_cmd, shell=True, check=True)
    else:
        lock.acquire()
        sys.stderr.write("Found existing mash database " + dbname + ".msh for k = " + str(k) + "\n")
        lock.release()

####################
# query a database #
####################

def nested_dict():
    return collections.defaultdict(nested_dict) # cannot easily pass lambda back and forth with pool.map

def runQuery(k, qFile, dbPrefix, self = True, mash_exec = 'mash', threads = 1):
    
    # define matrix for storage
    raw_k = nested_dict()
    
    # multithreading
    lock.acquire()
    sys.stderr.write("Querying mash database for k = " + str(k) + "\n")
    lock.release()
    
    # run mash distance query based on current file
    dbname = "./" + dbPrefix + "/" + dbPrefix + "." + str(k) + ".msh"
    
    try:
        mash_cmd = mash_exec + " dist -p " + str(threads)   # this should be harmonised with sketching function - will profile this
        if self:
            mash_cmd += " " + dbname + " " + dbname
        else:
            mash_cmd += " -l " + dbname + " " + qFile
        mash_cmd += " 2> " + dbPrefix + ".err.log"
        sys.stderr.write(mash_cmd)

        rawOutput = subprocess.Popen(mash_cmd, shell=True, stdout=subprocess.PIPE)

        for line in rawOutput.stdout.readlines():
            mashVals = line.decode().rstrip().split("\t")
            if (len(mashVals) > 2):
                if mashVals[0] != mashVals[1] and raw_k[mashVals[0]][mashVals[1]] is not None:
                    mashMatch = mashVals[-1].split('/')
                    raw_k[mashVals[1]][mashVals[0]] = float(mashMatch[0])/float(mashMatch[1])

    except subprocess.CalledProcessError as e:
        lock.acquire()
        sys.stderr.write("mash dist command failed; returned: "+e.message+"\n")
        lock.release()
        sys.exit(1)

    # return output
    return raw_k

# split list into unequally sized batches
def splitList(a, n, inc):
    # modified from https://stackoverflow.com/questions/35755608/split-a-python-list-logarithmically; alternatives available
    zr = len(a) # remaining number of elements to split into sublists
    st = 0 # starting index in the full list of the next sublist
    nr = n # remaining number of sublist to construct
    nc = 1 # number of elements in the next sublist
    #
    b=[]
    while (zr/nr >= nc and nr>1):
        b.append( a[st:st+nc] )
        st, zr, nr, nc = st+nc, zr-nc, nr-1, nc+inc
    #
    nc = int(zr/nr)
    for i in range(nr-1):
        b.append( a[st:st+nc] )
        st = st+nc
    #
    b.append( a[st:max(st+nc,len(a))] )
    return b

def readAssemblyList(fn, threads = 1):
    
    # parse raw file
    assemblyList = []
    assemblyIndices = {}
    index = 0
    with open(fn, 'r') as iFile:
        for line in iFile:
            assembly = line.rstrip()
            assemblyList.append(assembly)
            assemblyIndices[assembly] = index
            index = index + 1

    # batch data into arithmetically-sized chunks for multithreading
    assemblyBatches = {}
    if (threads == 1):
        assemblyBatches[0] = assemblyList
    elif (threads > 1):
        batch = 0
        batchIncrement = int(len(assemblyList)/threads)
        for batch, assemblies in enumerate(splitList(assemblyList,threads,batchIncrement)):
            assemblyBatches[batch] = assemblies

    # return values
    return assemblyList, assemblyIndices, assemblyBatches

# run comparisons between different batch sizes
def runComparison(inputList,queryIndices,refIndices,klist,rawMatches,jacobian,self=True):
    
    # store results
    number_dists = 0
    if self:
        for query in inputList:
            number_dists = number_dists+queryIndices[query]
    else:
        number_dists = len(inputList)*len(refIndices.keys())
    outDists = np.zeros((int(number_dists), 2))
    querySeqs = []
    refSeqs = []
    row = 0
    
    for query in inputList:
        for ref in refIndices.values():

            if (not self or queryIndices[query] > queryIndices[ref]):
                pairwise = []
                for i in range(len(klist)):
                    k = klist[i]
                    # calculate sketch size. Note log taken here
                    pairwise.append(np.log(rawMatches[i][query][ref]))
                # curve fit pr = (1-a)(1-c)^k
                # log pr = log(1-a) + k*log(1-c)
                distFit = optimize.least_squares(fun=lambda p, x, y: y - (p[0] + p[1] * x),
                                                 x0=[0.0, -0.01],
                                                 jac=lambda p, x, y: jacobian,
                                                 args=(klist, pairwise),
                                                 bounds=([-np.inf, -np.inf], [0, 0]))
                transformed_params = 1 - np.exp(distFit.x)

                # store output
                outDists[row][0] = transformed_params[0]
                outDists[row][1] = transformed_params[1]
                querySeqs.append(queryIndices[query])
                if self:
                    refSeqs.append(queryIndices[query])
                else:
                    refSeqs.append(refIndices[query])
                row += 1

    return(outDists,querySeqs,refSeqs)


def queryDatabase(qFile, klist, dbPrefix, self = True, mash_exec = 'mash', threads = 1):

    # initialise dictionary to keep distances in
    queryList, queryIndices, queryBatches = readAssemblyList(qFile,threads)

    # iterate through kmer lengths
    l = Lock()
    pool = Pool(processes=threads, initializer=init_lock, initargs=(l,))
    threadsPerPool = int(threads/len(klist)) # not sure this is a good idea?
    if threadsPerPool < 1:
        threadsPerPool = 1
    raw = pool.map(partial(runQuery,qFile = qFile, dbPrefix = dbPrefix, self = self, mash_exec = mash_exec,threads = threadsPerPool), klist)
    pool.close()
    pool.join()
    
    # iterate through first dict to get seq lists
    # and number of comparisons - fix this with
    # proper sequence indexing
    querySeqs = []
    refSeqs = []
    queryList = list(raw[0].keys())   # this can be optimised out
    refList = []                # and this
    refIndices = {}
    number_dists = 0
    for query in raw[0].keys():
        if (len(refList) == 0):
            refList = list(raw[0][query].keys())
            for i,r in enumerate(refList):
                refIndices[i] = r
        for ref in raw[0][query].keys():
            number_dists = number_dists + 1

    # Hessian = 0, so Jacobian for regression is a constant
    jacobian = -np.hstack((np.ones((klist.shape[0], 1)), klist.reshape(-1, 1)))

    # run pairwise analyses across kmer lengths
    pool = Pool(processes=threads, initializer=init_lock, initargs=(l,))
    dists = pool.map(partial(runComparison,queryIndices=queryIndices,refIndices=refIndices,klist=klist,rawMatches=raw,jacobian=jacobian,self=self), queryBatches.values())
    pool.close()
    pool.join()

    # merge outputs
    distMat = np.empty((0,2),dtype=float)
    for i in range(len(dists)):
        distMat = np.concatenate((distMat,dists[i][0]))
        queryList.append(dists[i][1])
        refList.append(dists[i][2])

    os.remove(dbPrefix + ".err.log")

    return(refSeqs, querySeqs, distMat, queryIndices, refIndices)

##############################
# write query output to file #
##############################

def printQueryOutput(rlist, qlist, qIndices, rIndices, X, outPrefix):

    # open output file
    outFileName = outPrefix + "/" + outPrefix + ".search.out"
    with open(outFileName, 'w') as oFile:
        oFile.write("\t".join(['Query', 'Reference', 'Core', 'Accessory']) + "\n")
        # add results
        for i, (query, ref) in enumerate(zip(qlist, rlist)):
            oFile.write("\t".join([qIndices[query], rIndices[ref], str(X[i,0]), str(X[i,1])]) + "\n")

