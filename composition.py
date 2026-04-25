"""Run composition logic for learning and testing RoRo decision policies."""

import copy
import datetime
import math
import numpy as np
import os
import pandas as pd
import statistics
import time

from instance_generator import Instance
from itertools import permutations
from model import Realization, Feature, Tree


# Function: Get features
def get_features(number_of_features=None, policy=None):
    """
    Returns a list of features based on the specified policy and number of features.
    
    Args:
        number_of_features (int, optional): The number of features to return. If None, returns all features. Defaults to None.
        policy (str, optional): The policy to determine the feature set. Defaults to None.

    Returns:
        list: A list of Feature objects based on the specified policy and number of features.
    """

    if policy == 'Feature Hierarchy (Generic)':
        f_set = [
            Feature(name='Unloading', sense='yes'),
            Feature(name='Double cycling ship', sense='yes'),
            Feature(name='Deck 1 (main deck)', sense='yes'),
            Feature(name='Path to lower deck', sense='yes'),
            Feature(name='Double cycling terminal', sense='yes'),
            Feature(name='Occupied adjacent positions', sense='min'),
            Feature(name='Tug-handled cargo', sense='yes'),    
            Feature(name='Total distance', sense='min'),
            Feature(name='Tug-to-cargo distance', sense='min')  
        ]
    else:
        f_set = [
            Feature(name='Unloading', sense='yes'),
            Feature(name='Double cycling ship', sense='yes'),
            Feature(name='Path to lower deck', sense='yes'),
            Feature(name='Deck 2 (upper deck)', sense='yes'),
            Feature(name='Occupied adjacent positions', sense='min'),
            Feature(name='Tug-handled cargo', sense='yes'),
            Feature(name='Total distance', sense='min'),
            Feature(name='Tug-to-cargo distance', sense='min'),
            Feature(name='Double cycling terminal', sense='yes'),
            Feature(name='Deck 1 (main deck)', sense='yes'),
            Feature(name='Deck 0 (lower deck)', sense='yes'),
            Feature(name='Loading', sense='yes'),
            Feature(name='Driver-handled cargo', sense='yes')
        ]

    # assign levels / hierarchy
    for level, f in enumerate(f_set):
        f.level = level

    if number_of_features is not None:

        return f_set[:number_of_features]

    else:

        return f_set


# Function: Current time
def current_time():
    """
    Returns the current time in the format HH:MM:SS.

    Returns:
        str: A string representing the current time.
    """
    # Get the current date and time using the datetime module
    current_datetime = datetime.datetime.now()

    # Format the current time as HH:MM:SS
    formatted_time = current_datetime.strftime("%H:%M:%S")

    return formatted_time


# Function: Add to aggregated results
def add_to_aggregated_results(kpis_as_dict, target_file):
    """
    Adds key performance indicators (KPIs) to an aggregated results file. 
    If the file already exists, it appends the new KPIs to the existing data.
    Args:        
        kpis_as_dict (dict): A dictionary containing the KPIs to be added. The keys should correspond to the column names in the target file.
        target_file (str): The file path of the target Excel file where the KPIs should be added. If the file does not exist, it will be created.
    """
    df_new = pd.DataFrame.from_dict(kpis_as_dict)

    if os.path.isfile(target_file):
        df_old = pd.read_excel(target_file)
        df_new = pd.concat([df_old, df_new], ignore_index=True)

    df_new.to_excel(target_file, index=False)


# Function: N best tree from learning data
def n_best_tree_from_learning_data(df_learning_data, features, policy, measure='mean', n=1):
    """
    Finds the n best trees from the learning data based on the specified measure.
    Args:
        df_learning_data (pd.DataFrame): A DataFrame containing the learning data, including the features and their corresponding performance measures.
        features (list): A list of Feature objects that represent the features used in the trees.
        policy (str): The policy for which the trees are being evaluated. This is used to filter the learning data if necessary.
        measure (str, optional): The performance measure to use for evaluating the trees. Defaults to 'mean'.
        n (int, optional): The number of best trees to return. Defaults to 1.
    """
    # Find best tree
    df_min = df_learning_data[df_learning_data[measure] == df_learning_data[measure].min()]
    
    if df_min.shape[0] > 1:
        print('Warning: Multiple best trees (continue with first tree)') 

    # Create tree
    t = Tree(features=features, policy=policy)
    
    # Levels and weights of features are stored in columns with name 'L feature_name' or 'W feature_name' in learning data
    t.stat = {}
    for column, value in df_min.iloc[0].items():
        if column[0] not in ['L', 'S', 'W']:
            t.stat[column] = value

        for f in t.features:
            if f.name in column:
                if 'L ' in column:
                    f.level = None if pd.isnull(value) else int(value)
                    break
                elif 'S ' in column:
                    f.sense = value
                    break
                elif 'W ' in column:
                    f.weight = value
                    break
                else:
                    print('Error')

    t.update_ordered_features()

    return t


# Class: Composition
class Composition:

    # Function: Init
    def __init__(self, row, plot_animation, plot_stowage_plan, print_console=False):
        bigM = 999999
        self.print_console = print_console

        self.measure = 'mean'

        self.do_testing = True if int(row['do_testing']) == 1 else False
        self.do_learning = True if int(row['do_learning']) == 1 else False
        self.plot_animation = plot_animation
        self.plot_stowage_plan = plot_stowage_plan

        # general parameters
        self.data_availability_level_text = row['data_availability_level']
        data_availability_level_text_to_level = {'Start-Finish': 1, 'Transit': 3, 'Movements': 5}
        self.data_availability_level = data_availability_level_text_to_level[self.data_availability_level_text]
        
        self.max_decisions_per_deck = bigM if pd.isnull(row['max_decisions_per_deck']) else int(row['max_decisions_per_deck'])
        self.instance_name = row['instance']  # instance: ship type, terminal type, etc.

        self.distribution_function_times = row['distribution_times'] # 'Average', 'Exp', 'Normal'

        if self.distribution_function_times == 'Avg':
            self.distribution_function_times = 'Average'

        # policy
        self.decision_policy = row['decision_policy']
        self.learning_policy = None if pd.isnull(row['learning_policy']) else row['learning_policy']
        self.policy = self.decision_policy

        if self.learning_policy is not None:
            self.policy += ' (' + self.learning_policy + ')'

        self.batch = None if pd.isnull(row['batch']) else int(row['batch'])

        # policy parameters
        self.number_of_features = None if pd.isnull(row['number_of_features']) else int(row['number_of_features'])

        self.skip_prob_tug = 0
        self.skip_prob_driver = 0

        # tree parameters
        self.features = get_features(policy=self.policy)

        # testing
        self.n_realizations = 0 if pd.isnull(row['n_realizations']) else int(row['n_realizations'])
        self.n_instances = 0 if pd.isnull(row['n_instances']) else int(row['n_instances'])

        # seeds
        self.seed = int(row['initial_seed'])
        self.rng = np.random.default_rng(seed=None)

        # name
        self.name = str(self.instance_name) + ' ' + self.data_availability_level_text + ' ' + self.policy
        self.name += ' N' + str(self.number_of_features) if self.number_of_features is not None else ''
        self.name += ' B' + str(self.batch) if self.batch is not None else ''

        # paths
        learning_folder = 'results/learning/'
        if not os.path.exists(learning_folder):
            os.makedirs(learning_folder)
        
        self.file_path_learning_data = learning_folder + self.name 
        
        if self.learning_policy == 'fixed':
            self.file_path_learning_data = self.file_path_learning_data.replace(str(self.instance_name), 'balanced')
            self.file_path_learning_data = self.file_path_learning_data.replace(self.learning_policy, 'greedy')

        self.file_path_learning_data += '.xlsx'

        testing_folder = 'results/testing/'
        if not os.path.exists(testing_folder):
            os.makedirs(testing_folder)
        self.file_path_testing_data = testing_folder + self.name + '.xlsx'

        # learning data
        self.learning_data = dict()

    # Function: Learn and test
    def learn_and_test(self):
        print('Composition: ' + self.name
              + ', distribution: ' + str(self.distribution_function_times)
              + ', N (I,R): (' + str(self.n_instances) + ',' + str(self.n_realizations) + ')'
              )

        if self.do_learning:
            if self.print_console:
                print(f" Learn with {self.n_instances} instances and {self.n_realizations} realizations per instance.")

            tree = None
            if self.learning_policy == 'greedy':
                self.learn_tree_via_greedy()

            elif self.learning_policy == 'enumeration':
                self.learn_tree_via_enumeration()

            elif self.learning_policy == 'random':
                self.learn_tree_via_random()

            elif self.learning_policy == 'simulated_annealing':
                self.learn_tree_via_simulated_annealing()                

            if self.print_console:
                try:
                    df = pd.read_excel(self.file_path_learning_data, sheet_name='learning_data')
                    tree = n_best_tree_from_learning_data(df_learning_data=df, features=self.features, measure=self.measure, policy=self.policy, n=1)

                    print('  -> best tree: ' + str(tree))
                    print('  -> ' + str(tree.stat))
                except:
                    print('Warning: Problem with learning data ' + str(self.file_path_learning_data))
                    pass

        if self.do_testing:
            if self.print_console:
                print(f" Test with {self.n_instances} instances and {self.n_realizations} realizations per instance.")

            if self.decision_policy in ['Random', 'Deck-Lane-Row']:
                tree = None

            else:
                df = pd.read_excel(self.file_path_learning_data, sheet_name='learning_data')

                tree = n_best_tree_from_learning_data(df_learning_data=df,
                                                      features=self.features,
                                                      measure=self.measure,
                                                      policy=self.policy)


            if self.print_console and tree is not None:
                # print(' -> best tree: ' + str(tree))
                print(' -> best tree (ordered): ' + str([f.name for f in tree.ordered_features]))
                print(' -> ' + str(tree.stat))

            self.test_with_tree(tree=tree, is_learning=False)

    # Function: Learn tree via random
    def learn_tree_via_random(self):

        if self.print_console:
            print(', Iterations=' + str(self.n_learning_iterations))

        for iteration in range(500):

            new_tree = self.create_random_tree()

            if self.print_console:
                print(' ' + str(iteration) + ' learn tree: ' + str(new_tree))


            self.test_with_tree(tree=new_tree,
                                is_learning=True,
                                iteration=iteration)

    # Function: Learn tree via enumeration
    def learn_tree_via_enumeration(self):

        all_enumerations = list(permutations(self.features, r=self.number_of_features))
        if self.print_console:
            print(', Enumerations (n!/(n-r)!): ' + str(len(all_enumerations)))

        # N=2 -> 156 enumerations -> :15 = 11 batches (ca. 5 h per batch) 
        # N=3 -> 1716 enumerations -> :80 = 22 batches (ca. 30 h per batch)
        # N=4 -> 17160 enumerations -> :? = ? batches 
        iterations_per_batch = 80
        
        first_iteration = max(0, (self.batch - 1) * iterations_per_batch)
        last_iteration = self.batch * iterations_per_batch

        if last_iteration > len(all_enumerations):
            if first_iteration > len(all_enumerations):
                considered_enumerations = []
            else:
                considered_enumerations = all_enumerations[first_iteration:]
        else:
            considered_enumerations = all_enumerations[first_iteration:last_iteration]

        iteration = first_iteration + 1 
        for iteration_features in considered_enumerations:

            new_tree = Tree(features=self.features, policy=self.policy)

            for f in new_tree.features:
                f.level = None

            for level, f in enumerate(list(iteration_features)):
                f.level = level

            new_tree.update_ordered_features()
            
            if self.print_console:
                print('learn tree: ' + str(new_tree))

            self.test_with_tree(tree=new_tree,
                                is_learning=True,
                                iteration=iteration)
            
            iteration += 1

    # Function: Learn tree via greedy
    def learn_tree_via_greedy(self):

        best_tree = Tree(features=self.features, policy=self.policy)

        learning_dict = {x: [] for x in ['iteration'] + [f.name for f in self.features]}

        for f in best_tree.features:
            f.level = None
            f.weight = 0

        remaining_features = [f for f in best_tree.features]
        best_tree.update_ordered_features()

        x = len(remaining_features)

        if self.print_console:
            print(', Max. Iterations=' + str(int(((x*(x+1))/2))))

        self.test_with_tree(tree=best_tree,
                            is_learning=True,                            
                            iteration=0)

        while len(remaining_features) > 0:
            # print('- Remaining Features: ' + str([f.name for f in remaining_features]))
            # print(learning_dict)

            iteration = len(remaining_features)
            best_tree_iteration = None
            best_feature = None

            learning_dict['iteration'].append(iteration)

            names_remaining_features = [f.name for f in remaining_features]
            for f in best_tree.features:
                if f.name not in names_remaining_features:
                    learning_dict[f.name].append(None)

            for f in remaining_features:
                iteration = round(iteration + 0.01, 2)

                new_tree = copy.deepcopy(best_tree)

                f1 = None
                for f1 in new_tree.features:
                    if f.name == f1.name:
                        f1.level = len(best_tree.ordered_features)
                        f1.weight = 1
                        new_tree.update_ordered_features()
                        break
                
                if self.print_console:
                    print('  # learn feature: ' + str(f1) + ', level=' + str(f1.level))

                self.test_with_tree(tree=new_tree,
                                    is_learning=True,
                                    iteration=iteration)

                learning_dict[f.name].append(new_tree.stat[self.measure])

                if best_tree_iteration is None or new_tree.stat[self.measure] < best_tree_iteration.stat[self.measure]:
                    best_tree_iteration = copy.deepcopy(new_tree)
                    best_feature = copy.deepcopy(f1)

            if best_tree_iteration is None:
                remaining_features = []
                print('Error: best_tree_iteration is None in Composition.learn_tree_via_greedy().')

            else:
                best_tree = copy.deepcopy(best_tree_iteration)
                if self.print_console:
                    print('   # new (best) tree: ' + str(best_tree))
                    print('     -> ' + str(best_tree.stat))

                excluded_feature_names = [best_feature.name]
                if best_feature.name == 'Loading':
                    excluded_feature_names.append('Unloading')
                elif best_feature.name == 'Unloading':
                    excluded_feature_names.append('Loading')
                elif best_feature.name == 'Tug-handled cargo':
                    excluded_feature_names.append('Driver-handled cargo')
                elif best_feature.name == 'Driver-handled cargo':
                    excluded_feature_names.append('Tug-handled cargo')
                elif 'Deck' in best_feature.name:
                    if sum(1 for f1 in remaining_features if 'Deck' in f1.name) == 2:
                        for f1 in remaining_features:
                            if 'Deck' in f1.name:
                                excluded_feature_names.append(f1.name)

                remaining_features = [f for f in remaining_features if f.name not in excluded_feature_names]

        # save learning data
        with pd.ExcelWriter(self.file_path_learning_data) as writer:
            # learning data
            df_learning_data = pd.DataFrame(self.learning_data)
            df_learning_data.to_excel(writer, sheet_name='learning_data', index=False)

            # structured learning data
            df_learning_structure = pd.DataFrame(learning_dict)
            df_learning_structure.to_excel(writer, sheet_name='learning_structure', index=False)

    # Function: Learn tree via simulated annealing
    def learn_tree_via_simulated_annealing(self):
        C_0 = 300           # 300
        C_1 = 0.7           # 0.7

        best_tree = None

        for iteration in range(self.n_learning_iterations):
            if iteration == 0:
                new_tree = self.create_random_tree()

            else: 
                # latest or best tree? probability latest tree = exp(-(new - best) / temperature)
                p_sa = math.exp(-(new_tree.stat[self.measure] - best_tree.stat[self.measure]) / (C_0 * (C_1 ** iteration)))

                if self.rng.choice([True, False], p=[p_sa, 1 - p_sa]):
                    # continue with tree from previous iteration ('new_tree')
                    pass
                else:
                    # use best tree so far
                    new_tree = copy.deepcopy(best_tree)

                new_tree.mutate_two_random_levels(random_state=self.rng)
                       
            self.test_with_tree(tree=new_tree,
                                is_learning=True,
                                iteration=iteration)

            if best_tree is None:

                best_tree = copy.deepcopy(new_tree)

            elif new_tree.stat[self.measure] < best_tree.stat[self.measure]:
                if self.print_console:
                    print('  # old best tree: ' + str(best_tree))
                    print('    -> ' + str(best_tree.stat))

                best_tree = copy.deepcopy(new_tree)

                if self.print_console:
                    print('  # new best tree: ' + str(best_tree))
                    print('    -> ' + str(best_tree.stat))

    # Function: Create random tree
    def create_random_tree(self):
        # deepcopy features
        new_features = copy.deepcopy(self.features)

        # set all features as irrelevant (default)
        for f in new_features:
            f.level = None
            f.weight = 0

        # draw features for tree and assign levels/weights
        features_in_tree = self.rng.choice(a=new_features, size=self.number_of_features, replace=False).tolist()

        for level, f in enumerate(features_in_tree):
            f.level = level
            f.weight = 1

        # create tree
        new_tree = Tree(features=new_features, policy=self.policy)
        
        return new_tree
    
    # Function: Test with tree
    def test_with_tree(self, tree, is_learning, iteration=1):
        start_time = time.time()

        testing_data = {}
        
        # instances
        instances = []

        for i_id in range(self.n_instances):
            instances.append(Instance(name=self.instance_name, seed=self.seed + i_id))

        # Plot stowage plan for first instance (if specified)
        if self.plot_stowage_plan and len(instances) > 0:
            instances[0].plot_stowage_plan() 
 
        # realizations
        for i in instances:
            for r_id in range(self.n_realizations):
                r = Realization(
                    id=r_id + 1,
                    composition=self,
                    instance=i,
                    tree=tree
                )

                r.solve(plot=self.plot_animation)

                r.add_to_results_data(results_data=testing_data)

        stat = {
            'iteration': iteration,
            'I': len(instances),
            'R': self.n_realizations,
            'mean': round(statistics.mean(testing_data['duration_in_min']), 4),
            'median': round(statistics.median(testing_data['duration_in_min']), 4),
            'stdev': round(statistics.stdev(testing_data['duration_in_min']), 4) if len(testing_data['duration_in_min']) > 1 else 0,
            'min': round(min(testing_data['duration_in_min']), 4),
            'max': round(max(testing_data['duration_in_min']), 4),
            'computation_time_in_sec': round(time.time() - start_time, 2)
        }   

        if tree is not None:
            tree.stat = stat

        if self.print_console:
            print('  ' + str(stat))

        # save data
        if is_learning:
            # learning data: statistics
            for key, value in stat.items():
                self.learning_data[key] = self.learning_data[key] + [value] if key in self.learning_data else [value]

            # learning data: features (weight or hierarchy)
            for f in tree.features:
                key = 'W ' + f.name if 'Feature Counting' in self.policy else 'L ' + f.name
                value = f.weight if 'Feature Counting' in self.policy else f.level
                self.learning_data[key] = self.learning_data[key] + [value] if key in self.learning_data else [value]

            # save as excel-file
            df = pd.DataFrame(self.learning_data)
            df = df.sort_values(by='mean')

            df.to_excel(self.file_path_learning_data,
                        sheet_name='learning_data',
                        index=False)
        
        else:
            # testing data
            df_new = pd.DataFrame.from_dict(testing_data)

            if os.path.isfile(self.file_path_testing_data):
                df_old = pd.read_excel(self.file_path_testing_data)
                df_new = pd.concat([df_old, df_new], ignore_index=True)

            df_new.to_excel(self.file_path_testing_data, index=False)
