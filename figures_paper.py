"""
Generate publication figures and summary tables from experiment results.

This module reads archived publication data from the `results_paper` folder.
That folder contains the result set used for the paper.

When you run new experiments yourself, outputs are written to the
`results` folder, which mirrors the same overall structure.
"""

import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scipy import stats
import statistics
import warnings

# Ignore future warnings from pandas (e.g., regarding the deprecation of the append method)
warnings.filterwarnings("ignore", category=FutureWarning)

# All figures are saved in this folder.
target_folder = 'results_paper/figures/'

translations = {
    'Random': 'Random',
    'Deck-Lane-Row': 'Deck-Lane-Row',
    'Feature Counting (greedy)': 'Feature Counting',
    'Feature Hierarchy (greedy)': 'Feature Hierarchy',
    'Feature Counting (fixed)': 'Feature Counting (Fix)',
    'Feature Hierarchy (fixed)': 'Feature Hierarchy (Fix)',
    #
    'balanced': 'Balanced', 
    'surplus_DC': 'Surplus DC', 
    'surplus_TC': 'Surplus TC',
    #
    'SP-Unknown': 'SP Unknown',
    'SP-Ratio': 'SP Cargo Ratio',
    'SP-Known': 'SP Known'
}

setting_color = {
        'Start-Finish': 'black',
        'Transit': 'lightgrey',
        'Movements': 'grey',
        #
        'Surplus DC': 'lightgrey', 
        'Balanced': 'black', 
        'Surplus TC': 'grey',
        #
        'SP-Unknown': 'lightgrey', 
        'SP-Ratio': 'black', 
        'SP-Known': 'grey'
    }

tick_turnaround_time = 20

font_dict_subplot = dict(
                          family='Times New Roman',
                          size=20,
                          color='black'
                      )

feature_hierarchy_value = 269.51


median_baseline_rnd = 295.27
median_baseline_dlr = 290.91
median_baseline_fc = 282.96
median_baseline_fh = 269.52

if not os.path.exists(target_folder):
    os.makedirs(target_folder)

# Function: Fig results main
def fig_results_main(name, do_pdf=False, fixed_policies=False):

    # Load all Testing-Data
    folder_path = 'results_paper/testing/'

    # Initialize an empty list to store DataFrames
    dfs = []

    # Loop through all files in the folder
    for file_name in os.listdir(folder_path):
        if file_name.endswith('.xlsx'):
            # Construct the full file path
            file_path = os.path.join(folder_path, file_name)
            
            # Read the Excel file into a DataFrame
            df = pd.read_excel(file_path)

            # Append the DataFrame to the list
            dfs.append(df)

    # Concatenate all DataFrames into one big DataFrame
    df = pd.concat(dfs, ignore_index=True)

    # Replace names 
    for old_value, new_value in translations.items():
        df.loc[df['policy'] == old_value, 'policy'] = new_value

    
    for old_value, new_value in translations.items():
        df.loc[df['instance'] == old_value, 'instance'] = new_value

    # all filtering-options
    if fixed_policies:
        policies = [
            'Feature Counting', 'Feature Counting (Fix)',
            'Feature Hierarchy', 'Feature Hierarchy (Fix)'
            ]

    else:
        policies = ['Random', 'Deck-Lane-Row',
                    'Feature Counting', 'Feature Hierarchy'
                    ]
    instances = ['Surplus DC', 'Balanced', 'Surplus TC']    # = Cargo Ratio
    data_availability_levels = ['Movements', 'Transit', 'Start-Finish']
    stowage_plans = ['SP-Ratio', 'SP-Known', 'SP-Unknown']  # SP-Ratio: using the policy learned for the specific ratio; SP-Known: using a policy 

    # sort df
    df.policy = df.policy.astype('category')
    df.policy = df.policy.cat.set_categories(policies)
    df = df.sort_values(by=['policy'], ascending=False)

    # save df
    # df.to_excel('results_paper/boxplot_results.xlsx')

    # create figure
    fig = go.Figure()

    # Each trace is a 'grouped' box-plozt
    # y-axis: policy
    # x-axis: turnaround time


    if name == 'fig_results_stowage_plan':
        data_availability_levels = ['Start-Finish']
        stowage_plans = ['SP-Ratio']
        if fixed_policies:
            instances = ['Surplus DC', 'Surplus TC']

        values = dict()

        for instance in instances:  

            filtered_df = df[(df['policy'].isin(policies)) & 
                        (df['instance'].isin([instance])) &
                        (df['stowage_plan'].isin(stowage_plans)) &
                        (df['data_availability_level'].isin(data_availability_levels))
                        ]

            fig.add_trace(go.Box(x=filtered_df['duration_in_min'].to_list(), 
                                y=filtered_df['policy'].to_list(), 
                                name=instance, 
                                marker=dict(color=setting_color[instance]), 
                                marker_line_color='black', 
                                showlegend=True, 
                                orientation='h'))

            values[instance] = filtered_df.groupby('policy')['duration_in_min'].apply(list).to_dict()

        # print(values)

        for instance in instances:   
            print('Instance', instance)
            if fixed_policies:
                comparisons = [['Feature Counting', 'Feature Counting (Fix)'], ['Feature Hierarchy', 'Feature Hierarchy (Fix)']]
            else:
                comparisons = [['Deck-Lane-Row', 'Random'], ['Feature Counting', 'Deck-Lane-Row'], ['Feature Hierarchy', 'Feature Counting']]
            for c in comparisons:
                # mean a < mean b
                a = values[instance][c[0]]
                b = values[instance][c[1]]
                results = stats.ttest_ind(a=a, b=b, alternative='less')
                print(' ', c[0], '<', c[1], '?')
                print('   mean', c[0], '=', round(statistics.mean(a), 2), ', mean', c[1], '=', round(statistics.mean(b), 2), ', statistic', round(results.statistic, 4), ', p-value', results.pvalue)

    elif name == 'fig_results_data_level_process':
        stowage_plans = ['SP-Ratio']
        instances = ['Balanced']

        for data_availability_level in data_availability_levels:  

            filtered_df = df[(df['policy'].isin(policies)) & 
                        (df['instance'].isin(instances)) &
                        (df['stowage_plan'].isin(stowage_plans)) &
                        (df['data_availability_level'].isin([data_availability_level]))
                        ]

            fig.add_trace(go.Box(x=filtered_df['duration_in_min'].to_list(), 
                                y=filtered_df['policy'].to_list(), 
                                name=data_availability_level, 
                                marker=dict(color=setting_color[data_availability_level]), 
                                marker_line_color='black', 
                                showlegend=True, 
                                orientation='h'))

    if name == 'fig_results_data_level_process':
        x_range = [220, 340]
    else:
        x_range = [200, 360]

    fig.update_layout(template='simple_white', 
                      width=1400, 
                      height=800,
                      xaxis=dict(
                          title='Turnaround Time [minutes]',
                          tickmode='linear',
                          range=x_range,
                          dtick=tick_turnaround_time,
                      ),
                      font=font_dict_subplot,
                      boxmode='group', 
                      legend={'x': 1, 'y': 1, 'traceorder': 'reversed'},
                      xaxis_title_font=dict(size=font_dict_subplot['size'])
                      )

    fig.update_traces(orientation='h') 

    fig.show()
    
    if do_pdf:
        target_name = name + ' (fixed)' if fixed_policies else name
        fig.write_html(target_folder + target_name + '.html')
        fig.write_image(target_folder + target_name + '.pdf')

# Function: Fig random hierarchies
def fig_random_hierarchies(do_pdf):
    name = 'fig_results_random_hierarchies'

    Ns = [4, 6, 8, 10]

    fig = go.Figure()

    for n in Ns:

        final_df = pd.DataFrame(columns=['iteration', 'N', 'seed', 'mean', 'median', 'stdev'])

            
        df = pd.read_excel('results_paper/learning/balanced SP-Ratio Start-Finish Feature Hierarchy (random) N' + str(n) + '.xlsx')
        df = df[['iteration', 'mean', 'median', 'stdev']]
        df['N'] = n

        final_df = pd.concat([final_df, df], ignore_index=True)

        fig.add_trace(go.Box(x=final_df['mean'], name=n, marker_color='grey', showlegend=False))

    text_size = 20
    fig.update_layout(template='simple_white', width=700, height=500,
                      xaxis=dict(
                          title='Turnaround Time [minutes]',
                          tickmode='linear',
                          range=[260, 340],
                          dtick=tick_turnaround_time
                      ),
                      yaxis=dict(
                          title='Number of Features [-]'
                      ),
                      font=font_dict_subplot,
                      xaxis_title_font=dict(size=text_size),
                      yaxis_title_font=dict(size=text_size),
                      title=None
                      )

    # Add vertical line    
    # Define the secondary y-axis
    fig.update_layout(
        yaxis2=dict(
            overlaying="y",
            side="right",
            showgrid=False,  # You can customize grid options as needed
            title="Secondary Axis",
            range=[0, 21],
            visible=False
        )
    )

    # Add dashed vertical line
    # fig.add_shape(type="line",x0=0,  x1=1, xref="paper", y0=median_baseline_fh, y1=median_baseline_fh, opacity=0.2, line=dict(color="darkred", width=8))

    fig.add_trace(go.Scatter(x=[median_baseline_fh, median_baseline_fh],
                            y=[0, 20.2],
                            mode="lines",
                            # line=dict(color="grey", dash="dash"),
                            opacity=0.2, line=dict(color="darkred", width=8),
                            showlegend=False,
                            yaxis="y2"  # This line will be plotted on the secondary axis
                            ))
    # fig.add_annotation(x=feature_hierarchy_value - 2, y=10, text="Greedy Search", textangle=-90, xref='x', yref='y2', showarrow=False)
    fig.add_annotation(x=feature_hierarchy_value + 10, y=21, text="Heuristic Hierarchy", xref='x', yref='y2', showarrow=False, font=dict(size=text_size))
    fig.update_layout(
        title='',  # Ensure no title text
        margin=dict(t=60)  # Adjust top margin to remove title entirely
    )
    
    fig.show()
    
    if do_pdf:
        fig.write_html(target_folder + name + '.html')
        fig.write_image(target_folder + name + '.pdf')

# Function: Fig results enumeration histogram
def fig_results_enumeration_histogram(do_pdf):
    name = 'fig_results_enumeration_histogram_N3'

    final_df = pd.DataFrame(columns=['iteration', 'batch', 'seed', 'mean', 'median', 'stdev'])


    for batch in [i+1 for i in range(22)]:
        df = pd.read_excel('results_paper/learning/balanced SP-Ratio Start-Finish Feature Hierarchy (enumeration) N3 B' + str(batch) + '.xlsx')

        df = df[['iteration', 'mean', 'median', 'stdev']]
        df['batch'] = batch

        final_df = pd.concat([final_df, df], ignore_index=True)

    final_df = final_df.sort_values('mean')
    final_df.to_excel('results_paper/learning/' + name + '.xlsx')

    print('Figure: ' + name + ', Size of DataFrame=' + str(len(final_df)))

    text_size = 20
    fig = px.histogram(final_df, 
                        x='mean', 
                        template='simple_white',
                        # cumulative=True,
                        # barnorm='percent',
                        # histnorm='percent',
                        # nbins=20,
                        color_discrete_sequence=['grey' for i in range(22)])
            
    fig.update_layout(template='simple_white', width=700, height=500,
                    xaxis=dict(
                        title='Turnaround Time [minutes]',
                        tickmode='linear',
                        range=[260, 340],
                        dtick=tick_turnaround_time
                    ),
                    yaxis=dict(
                        title='Permutations [-]',
                        range=[0, 400],
                        dtick=100
                    ),
                    font=font_dict_subplot,
                    xaxis_title_font=dict(size=text_size),
                    yaxis_title_font=dict(size=text_size)
                    )

    # Add vertical line    
    # Define the secondary y-axis
    fig.update_layout(
        yaxis2=dict(
            overlaying="y",
            side="right",
            showgrid=False,  # You can customize grid options as needed
            title="Secondary Axis",
            range=[0, 21],
            visible=False
        )
    )

    # Add dashed vertical line
    fig.add_trace(go.Scatter(x=[feature_hierarchy_value, feature_hierarchy_value],
                            y=[0, 20],
                            mode="lines",
                            # line=dict(color="grey", dash="dash"),
                            opacity=0.2, line=dict(color="darkred", width=8),
                            showlegend=False,
                            yaxis="y2"  # This line will be plotted on the secondary axis
                            ))
    # fig.add_annotation(x=feature_hierarchy_value - 2, y=10, text="Greedy Search", textangle=-90, xref='x', yref='y2', showarrow=False)
    fig.add_annotation(x=feature_hierarchy_value + 10, y=21, text="Heuristic Hierarchy", xref='x', yref='y2', showarrow=False, font=dict(size=text_size))

    fig.show()

    if do_pdf:
        fig.write_html(target_folder + name + '.html')
        fig.write_image(target_folder + name + '.pdf')

# Function: Tab hierarchies
def tab_hierarchies():

    feature_dict = {      
        # ORIGINAL ORDER  
        # 'L Driver-handled cargo': 'Driver-handled cargo?',
        # 'L Tug-handled cargo': 'Tug-handled cargo?',
        # #
        # 'L Deck 0 (lower deck)': 'Lower deck?',
        # 'L Deck 1 (main deck)': 'Main deck?',        
        # 'L Deck 2 (upper deck)': 'Upper deck?',
        # #
        # 'L Loading': 'Loading?',
        # 'L Unloading': 'Unloading?',
        # #
        # 'L Double cycling ship': 'Double cycling ship?',
        # 'L Double cycling terminal': 'Double cycling yard?',
        # 'L Path to lower deck': 'Path to lower deck?',
        # #
        # 'L Occupied adjacent positions': 'Min. occupied adjacent positions?',
        # 'L Total distance': 'Min. total distance?',
        # 'L Tug-to-cargo distance': 'Min. tug-to-cargo distance?'        

        # NEW ORDER
        'L Unloading': 'Unloading?',
        'L Double cycling ship': 'Double cycling ship?',
        'L Path to lower deck': 'Path to lower deck?',
        'L Double cycling terminal': 'Double cycling yard?',
        'L Deck 0 (lower deck)': 'Lower deck?', 
        'L Occupied adjacent positions': 'Min. occupied adjacent positions?',                        
        'L Deck 2 (upper deck)': 'Upper deck?',     
        'L Tug-handled cargo': 'Tug-handled cargo?',
        'L Total distance': 'Min. total distance?',
        'L Tug-to-cargo distance': 'Min. tug-to-cargo distance?',
        #
        'L Deck 1 (main deck)': 'Main deck?',  
        'L Loading': 'Loading?',
        'L Driver-handled cargo': 'Driver-handled cargo?'
    }

    ##########################
    #
    instances = [
        'surplus_DC',
        'balanced',
        'surplus_TC'
        ]

    final_dict = {
        'features': [feature_tab_name for feature, feature_tab_name in feature_dict.items()]
    }

    final_dict = dict()

    for instance in instances:

        final_dict[instance] = {feature_tab_name: -1 for feature, feature_tab_name in feature_dict.items()}
                    
        path = 'results_paper/learning/' + instance + ' SP-Ratio Start-Finish Feature Hierarchy (greedy).xlsx'
        print(path)

        df = pd.read_excel(path)
        df = df.sort_values('mean')

        first_row = df.iloc[0]

        for feature, feature_tab_name in feature_dict.items():
            for column_name, value in first_row.items():                    
                if column_name == feature:

                    if pd.isnull(value):
                        hiearchy_level = -1
                    else:
                        hiearchy_level = int(value) + 1

                    final_dict[instance][feature_tab_name] = hiearchy_level

    # tab_value = '$' + str(hiearchy_level) + '~ (\\uparrow)$'
    for instance in ['surplus_DC', 'surplus_TC']:
        for feature, feature_tab_name in feature_dict.items():
            if final_dict[instance][feature_tab_name] == -1:
                if final_dict['balanced'][feature_tab_name] == -1:
                    final_dict[instance][feature_tab_name] = '$-$'
                else:
                    final_dict[instance][feature_tab_name] = '$-~ (\\downarrow)$'
            elif final_dict['balanced'][feature_tab_name] == -1:
                final_dict[instance][feature_tab_name] = '$' + str(final_dict[instance][feature_tab_name]) + '~ (\\uparrow)$'
            elif final_dict[instance][feature_tab_name] < final_dict['balanced'][feature_tab_name]:
                final_dict[instance][feature_tab_name] = '$' + str(final_dict[instance][feature_tab_name]) + '~ (\\uparrow)$'
            elif final_dict[instance][feature_tab_name] > final_dict['balanced'][feature_tab_name]:
                final_dict[instance][feature_tab_name] = '$' + str(final_dict[instance][feature_tab_name]) + '~ (\\downarrow)$'
            else:
                final_dict[instance][feature_tab_name] = '$' + str(final_dict[instance][feature_tab_name]) + '$'

    for instance in ['balanced']:
        for feature, feature_tab_name in feature_dict.items():
            if final_dict[instance][feature_tab_name] == -1:
                final_dict[instance][feature_tab_name] = '$-$'
            else:
                final_dict[instance][feature_tab_name] = '$' + str(final_dict[instance][feature_tab_name]) + '$'

    df = pd.DataFrame.from_dict(final_dict)
    print(df)
    
    df['balanced'] = df['balanced'].astype(str).replace('-1', '$~$')

    df.reset_index(inplace=True)
    df.rename(columns={'index': 'Feature'}, inplace=True)

    print(df.to_latex(index=False))

# Function: Create df with all results
def create_df_with_all_results():
    # Load all Testing-Data
    folder_path = 'results_paper/testing'

    # Initialize an empty list to store DataFrames
    dfs = []

    # Loop through all files in the folder
    for file_name in os.listdir(folder_path):
        if file_name.endswith('.xlsx'):
            # Construct the full file path
            file_path = os.path.join(folder_path, file_name)
            
            # Read the Excel file into a DataFrame
            df = pd.read_excel(file_path)

            # Append the DataFrame to the list
            dfs.append(df)

    # Concatenate all DataFrames into one big DataFrame
    df = pd.concat(dfs, ignore_index=True)

    # Replace names 
    for old_value, new_value in translations.items():
        df.loc[df['policy'] == old_value, 'policy'] = new_value

    
    for old_value, new_value in translations.items():
        df.loc[df['instance'] == old_value, 'instance'] = new_value


    df.rename(columns={'instance': 'cargo_ratio'}, inplace=True)

    df.to_excel('results_paper/all_results.xlsx', index=False)

# Function: Figure baseline
def figure_baseline(do_pdf):
    # Load testing data
    df = pd.read_excel('results_paper/all_results.xlsx')

    # all filtering-options
    policies = ['Random', 'Deck-Lane-Row', 'Feature Counting', 'Feature Hierarchy']
    cargo_ratios = ['Surplus DC', 'Balanced', 'Surplus TC']    # = Cargo Ratio
    stowage_plans = ['SP-Ratio', 'SP-Known', 'SP-Unknown']  # SP-Ratio: using the policy learned for the specific ratio; SP-Known: using a policy 
    data_availability_levels = ['Movements', 'Transit', 'Start-Finish']

    # Baseline
    filtered_df = df[(df['policy'].isin(['Random', 'Deck-Lane-Row', 'Feature Counting', 'Feature Hierarchy'])) & 
                     (df['cargo_ratio'].isin(['Balanced'])) &
                     (df['stowage_plan'].isin(['SP-Ratio'])) &
                     (df['data_availability_level'].isin(['Start-Finish']))
                    ]
    print(f"Number of entries (Balanced): {len(filtered_df)}")

    # Rename policies
    policy_rename_map = {
        "Deck-Lane-Row": "DLR",
        "Feature Counting": "FC",
        "Feature Hierarchy": "FH",
        "Random": "RND"
    }

    # Apply the mapping to create a new column or overwrite the existing one
    filtered_df['policy'] = filtered_df['policy'].replace(policy_rename_map)

    fig = px.box(filtered_df, 
                 x="policy", 
                 y='duration_in_min', 
                 color="policy", 
                 color_discrete_map={"RND": "black", "DLR": "teal", "FC": "darkgoldenrod", "FH": "darkred"},
                 category_orders={"policy": ['RND', 'DLR', 'FC', 'FH']}
                 )
    
    text_size = 20
    fig.update_layout(template='simple_white', 
                      width=700, 
                      height=500,
                      xaxis=dict(title='Policy'),
                      yaxis=dict(
                          title='Turnaround Time [minutes]',
                          tickmode='linear',
                          range=[250,330],
                          dtick=tick_turnaround_time,
                      ),
                      font=font_dict_subplot,
                      legend=dict(
                          orientation='h',     # Horizontal legend
                          x=0.5,               # Centered horizontally
                          y=1.0,              # Position below the plot
                          xanchor='center',    # Anchor legend at center for x
                          yanchor='bottom',        # Anchor at top for y to align properly
                          title='',
                          font=dict(size=text_size)
                      ),
                      xaxis_title_font=dict(size=text_size),
                      yaxis_title_font=dict(size=text_size)
                      )
    
    fig.show()   

    if do_pdf:
        fig.write_html(target_folder + "figure_baseline" + '.html')
        fig.write_image(target_folder + "figure_baseline" + '.pdf')

# Function: Figure cargo ratio
def figure_cargo_ratio(do_pdf):
    # Load testing data
    df = pd.read_excel('results_paper/all_results.xlsx')

    # Filter data
    filtered_df = df[(df['policy'].isin(['Feature Counting', 'Feature Hierarchy'])) & 
                     (df['cargo_ratio'].isin(['Surplus DC', 'Surplus TC'])) &
                     (df['stowage_plan'].isin(['SP-Ratio'])) &
                     (df['data_availability_level'].isin(['Start-Finish']))
                     ]

    # Create figure
    fig = px.box(filtered_df, x="cargo_ratio", y='duration_in_min', color="policy", 
                 color_discrete_map={"Feature Counting": "darkgoldenrod", "Feature Hierarchy": "darkred"})

    fig.add_shape(type="line",x0=0,  x1=1, xref="paper", y0=median_baseline_fh, y1=median_baseline_fh, opacity=0.2, line=dict(color="darkred", width=8))

    text_size= 20

    fig.add_annotation(x=1, y=median_baseline_fh, xref='paper', yref='y', text='Baseline (FC)',
    showarrow=False,
    xanchor='right',  # align text to the left of the point
    yanchor='top', # align text vertically
    font=dict(color='black', size=text_size)
    )
    
    fig.update_layout(template='simple_white', 
                      width=700, 
                      height=500,
                      xaxis=dict(title='Cargo Ratio'),
                      yaxis=dict(
                          title='Turnaround Time [minutes]',
                          tickmode='linear',
                          range=[210,340],
                          dtick=tick_turnaround_time,
                      ),
                      font=font_dict_subplot,
                      legend=dict(
                          orientation='h',     # Horizontal legend
                          x=0.5,               # Centered horizontally
                          y=1.0,              # Position below the plot
                          xanchor='center',    # Anchor legend at center for x
                          yanchor='bottom',        # Anchor at top for y to align properly
                          title='',
                          font=dict(size=text_size)
                      ),
                      xaxis_title_font=dict(size=text_size),
                      yaxis_title_font=dict(size=text_size)
                      
                      )

    fig.show()
    if do_pdf:
        fig.write_html(target_folder + "figure_cargo_ratio" + '.html')
        fig.write_image(target_folder + "figure_cargo_ratio" + '.pdf')

# Function: Figure information process time
def figure_information_process_time(do_pdf):
    # Load testing data
    df = pd.read_excel('results_paper/all_results.xlsx')

    # Filter data
    filtered_df = df[(df['policy'].isin(['Feature Counting', 'Feature Hierarchy'])) & 
                     (df['cargo_ratio'].isin(['Balanced'])) &
                     (df['stowage_plan'].isin(['SP-Ratio'])) &
                     (df['data_availability_level'].isin(['Movements', 'Transit']))
                     ]
    
    # Create figure
    fig = px.box(filtered_df, x="data_availability_level", y='duration_in_min', color="policy", 
                 color_discrete_map={"Feature Counting": "darkgoldenrod", "Feature Hierarchy": "darkred"},
                 category_orders={"data_availability_level": ['Transit', 'Movements']})

    fig.add_shape(type="line",x0=0,  x1=1, xref="paper", y0=median_baseline_fh, y1=median_baseline_fh, opacity=0.2, line=dict(color="darkred", width=8))

    text_size = 20
    fig.add_annotation(x=1, y=median_baseline_fh, xref='paper', yref='y', text='Baseline (FC)',
    showarrow=False,
    xanchor='right',  # align text to the left of the point
    yanchor='top', # align text vertically
    font=dict(color='black', size=text_size)
    )
    
    fig.update_layout(template='simple_white', 
                      width=700, 
                      height=500,
                      xaxis=dict(title='Process-time Scenario'),
                      yaxis=dict(
                          title='Turnaround Time [minutes]',
                          tickmode='linear',
                          range=[220,290],
                          dtick=tick_turnaround_time,
                      ),
                      font=font_dict_subplot,
                      legend=dict(
                          orientation='h',     # Horizontal legend
                          x=0.5,               # Centered horizontally
                          y=1.0,              # Position below the plot
                          xanchor='center',    # Anchor legend at center for x
                          yanchor='bottom',        # Anchor at top for y to align properly
                          title='',
                          font=dict(size=text_size)
                      ),
                      xaxis_title_font=dict(size=text_size),
                      yaxis_title_font=dict(size=text_size)
                      )

    fig.show()
    if do_pdf:
        fig.write_html(target_folder + "figure_information_process_time" + '.html')
        fig.write_image(target_folder + "figure_information_process_time" + '.pdf')

# Function: Figure information stowage plan
def figure_information_stowage_plan(do_pdf):
    # Load testing data
    df = pd.read_excel('results_paper/all_results.xlsx')

    # Filter data
    filtered_df = df[(df['policy'].isin(['Feature Hierarchy', 'Feature Hierarchy (Fix)'])) & 
                     (df['cargo_ratio'].isin(['Surplus DC', 'Surplus TC'])) &
                     (df['stowage_plan'].isin(['SP-Ratio'])) &
                     (df['data_availability_level'].isin(['Start-Finish']))
                     ]
    # print(len(filtered_df))

    # Create figure
    fig = px.box(filtered_df, x="cargo_ratio", y='duration_in_min', color="policy", 
                 color_discrete_map={"Feature Hierarchy": "darkred", "Feature Hierarchy (Fix)": "forestgreen"},
                 category_orders={"policy": ['Feature Hierarchy', 'Feature Hierarchy (Fix)']})

    fig.add_shape(type="line",x0=0,  x1=1, xref="paper", y0=median_baseline_fh, y1=median_baseline_fh, opacity=0.2, line=dict(color="darkred", width=8))

    text_size = 20
    fig.add_annotation(x=1, y=median_baseline_fh, xref='paper', yref='y', text='Baseline (FC)',
    showarrow=False,
    xanchor='right',  # align text to the left of the point
    yanchor='top', # align text vertically
    font=dict(color='black', size=text_size)
    )
    
    fig.update_layout(template='simple_white', 
                      width=700, 
                      height=500,
                      xaxis=dict(title='Cargo Ratio'),
                      yaxis=dict(
                          title='Turnaround Time [minutes]',
                          tickmode='linear',
                          range=[210,340],
                          dtick=tick_turnaround_time,
                      ),
                      font=font_dict_subplot,
                      legend=dict(
                          orientation='h',     # Horizontal legend
                          x=0.5,               # Centered horizontally
                          y=1.0,              # Position below the plot
                          xanchor='center',    # Anchor legend at center for x
                          yanchor='bottom',        # Anchor at top for y to align properly
                          title='',
                          font=dict(size=text_size)
                      ),
                      xaxis_title_font=dict(size=text_size),
                      yaxis_title_font=dict(size=text_size)
                      )

    fig.show()
    if do_pdf:
        fig.write_html(target_folder + "figure_information_stowage_plan" + '.html')
        fig.write_image(target_folder + "figure_information_stowage_plan" + '.pdf')

# Function: Main
def main():
    do_pdf = True

    # figure_baseline(do_pdf)
    # figure_cargo_ratio(do_pdf)

    # figure_information_process_time(do_pdf)
    # figure_information_stowage_plan(do_pdf)

    fig_random_hierarchies(do_pdf=do_pdf)
    fig_results_enumeration_histogram(do_pdf=do_pdf)

    # fig_results_main(name='fig_results_stowage_plan', do_pdf=do_pdf)
    # fig_results_main(name='fig_results_stowage_plan', fixed_policies=True, do_pdf=do_pdf)
    # fig_results_main(name='fig_results_data_level_process', do_pdf=do_pdf)

    # tab_hierarchies()


if __name__ == '__main__':
    main()