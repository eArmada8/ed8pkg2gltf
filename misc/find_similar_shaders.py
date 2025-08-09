# ED8 shader finder.  Give the filename of a shader e.g. 'ed8_chr.fx#43908C853D966A373118677862503A56'
# and it will search the database (by default 'all_shaders.csv', set below) to generate a report
# of the other switches, ranked by similarity.  Requires Python 3.10 or newer.
#
# Requires all_shaders.csv, obtain from
# https://github.com/eArmada8/ed8pkg2gltf/raw/main/doc/game_transfer_img/all_shaders.csv
#
# GitHub eArmada8/ed8pkg2gltf

import os, csv
import argparse

csv_file = 'all_shaders.csv'

class Shader_db:
    def __init__(self, shader_db_csv, report_file = 'report.txt'):
        self.shader_db_csv = shader_db_csv
        self.report_file = report_file
        self.shader_array = self.read_shader_csv()
        self.shader_switches = self.shader_array[0][6:]
        self.shader_sig = {x[0]:''.join(x[6:]) for x in self.shader_array[1:]}
        self.diffs = {}
        self.restriction = ''
        self.restriction_column = None
        self.restricted_list = [x[0] for x in self.shader_array[1:]]
        self.report = ''

    def read_shader_csv (self):
        with open(self.shader_db_csv) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            return([row for row in csv_reader])

    def set_restricted_list (self, restriction):
        if restriction in self.shader_array[0][1:6]:
            self.restriction = restriction
            self.restriction_column = self.shader_array[0].index(restriction)
            self.restricted_list = [x[0] for x in self.shader_array[1:] if x[self.restriction_column] != 'None']
        else:
            self.restriction_column = None
            self.restricted_list = [x[0] for x in self.shader_array[1:]]
        return

    def diff(self, shader1, shader2): #Returns the value of shader2
        string1 = self.shader_sig[shader1]
        string2 = self.shader_sig[shader2]
        differences = [i for i in range(len(string1)) if string1[i] != string2[i]]
        return({self.shader_switches[i]:string2[i] for i in differences})

    def sort_shaders_by_similarity(self, shader):
        shader_diff = {k:(int(self.shader_sig[k], base=2) ^ int(self.shader_sig[shader], base=2)).bit_count() \
            for k in self.shader_sig if k != shader}
        diff_val = sorted(list(set(shader_diff.values())))
        self.diffs = {diff_val[i]:{x:self.diff(shader,x) for x in shader_diff if shader_diff[x] == diff_val[i]}\
            for i in range(len(diff_val))}

    def format_report(self, shader):
        self.report = 'Original Shader: {0}\n'.format(shader)
        if self.restriction != '':
            self.report += '\nRestriction: {} is not None\n'.format(self.restriction)
        array_first_column = [x[0] for x in self.shader_array]
        for i in self.diffs:
            if len([j for j in self.diffs[i] if j in self.restricted_list]) > 0:
                self.report += '\nShaders with {} differences:\n\n'.format(i)
                for j in self.diffs[i]:
                    if j in self.restricted_list:
                        self.report += '{}:'.format(j)
                        if self.restriction_column != None:
                            row = array_first_column.index(j)
                            self.report += ' (available in {})\n'.format(self.shader_array[row][self.restriction_column])
                        else:
                            self.report += '\n'
                        self.report += '\n'.join(['{0}: {1}'.format(k,v) for (k,v)\
                            in self.diffs[i][j].items()]) + '\n\n'
        return(self.report)

    def generate_report(self, shader, write_file):
        self.sort_shaders_by_similarity(shader)
        if write_file:
            with open(self.report_file,'w') as f:
                f.write(self.format_report(shader))
        else:
            for i in self.diffs:
                if len([j for j in self.diffs[i] if j in self.restricted_list]) > 0:
                    for j in self.diffs[i]:
                        if j in self.restricted_list:
                            # print any since we are lacking a good heuristic for the "best"
                            print(j)
                            return
        return

if __name__ == "__main__":
    # Set current directory
    os.chdir(os.path.abspath(os.path.dirname(__file__)))
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--shader', type=str, help="shader to find, e.g.ed8.fx#CE03DCE5DFEF5F7C4FB6937519B03034")
    parser.add_argument('-g', '--game', type=str, help="game in which to find a similar shader, any of {cs1,cs2,cs3,cs4,cs5}")
    parser.add_argument('--no-report', action='store_false', dest='write_file', help="prints a single most similar shader to stdout (any if there are multiple)")
    args = parser.parse_args()

    if os.path.exists(csv_file):
        shader_db = Shader_db(csv_file)
        shader = args.shader
        if not shader:
            shader = input("Please enter name of shader to analyze: ")
        while not shader in shader_db.shader_sig.keys():
            partial_matches = [x for x in shader_db.shader_sig.keys() if shader.upper() in x]
            if len(partial_matches) > 0: # We will only take the first
                confirm = input("{0} not found, did you mean {1}? (y/N) ".format(shader, partial_matches[0]))
                if confirm.lower() == 'y':
                    shader = partial_matches[0]
                else:
                    shader = input("Please enter name of shader to analyze: ")
            else:
                shader = input("Invalid entry. Please enter name of shader to analyze: ")
        restriction = args.game
        if not restriction:
            restriction = input("Please enter game restriction [{}, or blank for None]: ".format(', '.join(shader_db.shader_array[0][1:6])))
        while not restriction in ['']+shader_db.shader_array[0][1:6]:
            restriction = input("Invalid entry. Please enter game restriction [{}, or blank for None]: ".format(', '.join(shader_db.shader_array[0][1:6])))
        shader_db.set_restricted_list(restriction)
        shader_db.report_file = 'report_{0}_{1}.txt'.format(shader_db.restriction,shader)
        shader_db.generate_report(shader, args.write_file)
    else:
        input("{} is missing!  Press Enter to abort.".format(csv_file))
