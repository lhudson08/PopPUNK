#!/usr/bin/env python
# Copyright 2018 John Lees and Nick Croucher

"""Tests for PopPUNK"""

import subprocess
import os
import sys
import shutil

mash_exec = 'mash'
if len(sys.argv) > 1:
    mash_exec = sys.argv[1]

if not os.path.isfile("12754_4#89.contigs_velvet.fa"):
    sys.stderr.write("Extracting example dataset\n")
    subprocess.run("tar xf example_set.tar.bz2", shell=True, check=True)

#easy run
sys.stderr.write("Running database creation + BGMM model fit (--easy-run)\n")
subprocess.run("python ../poppunk-runner.py --easy-run --r-files references.txt --min-k 13 --k-step 3 --output example_db --full-db --K 4 --no-stream --mash " + mash_exec, shell=True, check=True)

#fit dbscan
sys.stderr.write("Running HDBSCAN model fit (--fit-model)\n")
subprocess.run("python ../poppunk-runner.py --fit-model --distances example_db/example_db.dists --ref-db example_db --output example_db --dbscan --microreact --cytoscape --no-stream --mash " + mash_exec, shell=True, check=True)

#refine model
sys.stderr.write("Running model refinement (--refine-model)\n")
subprocess.run("python ../poppunk-runner.py --refine-model --distances example_db/example_db.dists --ref-db example_db --output example_refine --neg-shift 0.8 --full-db --mash " + mash_exec, shell=True, check=True)

#assign query
sys.stderr.write("Running query assignment (--assign-query)\n")
subprocess.run("python ../poppunk-runner.py --assign-query --q-files references.txt --ref-db example_db --output example_query --no-stream --mash " + mash_exec, shell=True, check=True)

sys.stderr.write("Tests completed\n")

