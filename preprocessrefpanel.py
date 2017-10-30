from __future__ import print_function, division
import argparse, gc
import numpy as np
import pandas as pd
import gprim.dataset as gd
import pyutils.memo as memo
import config


def main(args):
    # basic initialization
    mhc = [25684587, 35455756]
    refpanel = gd.Dataset(args.bfile_chr)

    # read in ld blocks, remove MHC, read SNPs to print
    ldblocks = pd.read_csv(args.ld_blocks, delim_whitespace=True, header=None,
            names=['chr','start', 'end'])
    mhcblocks = (ldblocks.chr == 'chr6') & (ldblocks.end > mhc[0]) & (ldblocks.start < mhc[1])
    ldblocks = ldblocks[~mhcblocks]
    print(len(ldblocks), 'loci after removing MHC')
    print_snps = pd.read_csv(args.print_snps, header=None, names=['SNP'])
    print_snps['printsnp'] = True
    print(len(print_snps), 'print snps')

    for c in args.chroms:
        print('loading chr', c, 'of', args.chroms)
        # get refpanel snp metadata for this chromosome
        snps = refpanel.bim_df(c)
        snps = pd.merge(snps, print_snps, on='SNP', how='left')
        snps.printsnp.fillna(False, inplace=True)
        print(len(snps), 'snps in refpanel', len(snps.columns), 'columns, including metadata')

        for ldblock, X, meta, _ in refpanel.block_data(ldblocks, c, meta=snps):
            if meta.printsnp.sum() == 0:
                print('no print snps found in this block')
                continue
            mask = meta.printsnp.values
            X_ = X[:,mask]

            print('\tcomputing SVD of R_print')
            def rightsvd(A):
                try:
                    U_, svs_, _ = np.linalg.svd(A.T); svs_ = svs_**2 / A.shape[0]
                except np.linalg.linalg.LinAlgError:
                    print('\t\tresorting to svd of XTX')
                    U_, svs_, _ = np.linalg.svd(A.T.dot(A)); svs_ = svs_ / A.shape[0]
                return U_, svs_

            U_, svs_ = rightsvd(X_)
            k = np.argmax(np.cumsum(svs_)/svs_.sum() >= args.spectrum_percent / 100.)
            print('\treduced rank of', k, 'out of', meta.printsnp.sum(), 'printed snps')
            np.savez('{}{}.R'.format(args.outstem, ldblock.name), U=U_[:,:k], svs=svs_[:k])

            print('\tcomputing R2_print')
            R2 = X_.T.dot(X.dot(X.T)).dot(X_) / X.shape[0]**2
            print('\tcomputing SVD of R2_print')
            R2_U, R2_svs, _ = np.linalg.svd(R2)
            k = np.argmax(np.cumsum(R2_svs)/R2_svs.sum() >= args.spectrum_percent / 100.)
            print('\treduced rank of', k, 'out of', meta.printsnp.sum(), 'printed snps')
            np.savez('{}{}.R2'.format(args.outstem, ldblock.name),
                    U=R2_U[:,:k], svs=R2_svs[:k])

        del snps; memo.reset(); gc.collect()
    print('done')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--spectrum-percent', type=float, default=95,
            help='Determines how many eigenvectors are kept in the truncated SVD. ' +\
                    'A value of x means that x percent of the eigenspectrum will be kept. '+\
                    'Default value: 95')
    parser.add_argument('--outstem', default='/groups/price/ldsc/reference_files/' + \
            '1000G_EUR_Phase3/svds_95percent/',
            help='stem for output filenames')
    parser.add_argument('--chroms', nargs='+', default=range(1,23), type=int)

    parser.add_argument('--config', default=None,
            help='Path to a json file with values for other parameters. ' +\
                    'Values in this file will be overridden by any values passed ' +\
                    'explicitly via the command line.')
    parser.add_argument('--bfile-chr', default=None,
            help='Path to plink bfile of reference panel to use, not including ' +\
                    'chromosome number. If not supplied, will be read from config file.')
    parser.add_argument('--print-snps', default=None,
            help='Path to set of potentially typed SNPs. If not supplied, will be read '+\
                    'from config file.')
    parser.add_argument('--ld-blocks', default=None,
            help='Path to UCSC bed file containing one bed interval per LD block. If '+\
                    'not supplied, will be read from config file.')

    args = parser.parse_args()
    config.add_default_params(args)
    main(args)
