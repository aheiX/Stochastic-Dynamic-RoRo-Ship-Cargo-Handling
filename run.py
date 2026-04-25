"""Entry point to execute configured compositions, optionally in parallel."""

import cProfile
import multiprocessing as mp
import pandas as pd
import pstats
import sys
import warnings

from composition import Composition
from timeit import default_timer

# Ignore future warnings from pandas (e.g., regarding the deprecation of the append method)
warnings.simplefilter(action='ignore', category=FutureWarning)


# Function: Run row
def run_row(c_row, plot_animation=False, plot_stowage_plan=False, print_console=False, print_pool_id=False):
    if c_row['do_testing'] or c_row['do_learning']:

        if print_pool_id:
            print('Pool ID: ' + str(mp.current_process()))

        c = Composition(row=c_row, plot_animation=plot_animation, 
                        plot_stowage_plan=plot_stowage_plan, 
                        print_console=print_console)
        
        c.learn_and_test()

        print('Completed: ' + str(c.name))


# Function: Run with profile
def run_with_profile(c_row):
    if c_row['do_testing'] or c_row['do_learning']:
        # Run the profiler
        cProfile.run('run_row(c_row=c_row)', 'profile_stats')

        # Create a Stats object from the profile data
        stats = pstats.Stats('profile_stats')

        # Sort the statistics by cumulative time spent in each function
        # stats.sort_stats('cumulative')
        stats.sort_stats('tottime')

        # Print the statistics
        stats.print_stats(10)


# Function: Run example
def run_example(plot_animation=False, plot_stowage_plan=False, print_console=False):
    start = default_timer()

    df_run = pd.read_excel('compositions_input_example.xlsx', sheet_name='runs', skiprows=1)

    for _, c_row in df_run.iterrows():
        run_row(
            c_row=c_row,
            plot_animation=plot_animation,
            plot_stowage_plan=plot_stowage_plan,
            print_console=print_console,
        )

        # Uncomment to run with profile
        # run_with_profile(c_row=c_row)

    print('elapsed time:', round(default_timer() - start, 4))


# Function: Run full compositions
def run_full_compositions(server):
    start = default_timer()

    df_run = pd.read_excel('compositions_input.xlsx', sheet_name='runs', skiprows=1)

    # max. 10 processses for CAU-Server 71 & 72
    # max. 12 processses for CAU-Server 66 & 67

    if int(server) in [71, 72]:
        pool = mp.Pool(processes=10)
    else:
        pool = mp.Pool(processes=12)

    for _, c_row in df_run.iterrows():
        if c_row['server'] == server:

            # Run in parallel on the server
            pool.apply_async(run_row, args=(c_row, False, False, False, True))

    pool.close()
    pool.join()

    print('elapsed time:', round(default_timer() - start, 4))


if __name__ == '__main__':
    mode = 'example' # example or full

    if mode == 'example':
        run_example(plot_animation=False, plot_stowage_plan=False, print_console=True)
    else:
        run_full_compositions(server=71)
