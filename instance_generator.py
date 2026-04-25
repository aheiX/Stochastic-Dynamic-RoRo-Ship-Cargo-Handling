"""Build stochastic RoRo terminal and ship instances used in simulations."""

import numpy as np
import pandas as pd


# Function: Get position by index
def get_position_by_index(positions, lane, row, deck=None):
    for r_pos in positions:
        if r_pos.lane == lane and r_pos.row == row and r_pos.deck == deck:
            return r_pos

    return None


# Class: Task
class Task:

    # Function: Init
    def __init__(self, source, target, cargo, vehicle, type):
        self.source = source
        self.target = target
        self.cargo = cargo
        self.vehicle = vehicle
        self.type = type

        self.data_availability_level = None
        self.distance_in_m = self.get_distance_in_m()
        self.duration_in_sec = None

    # Function: Get distance in m
    def get_distance_in_m(self):
        if self.type == 'moving':
            p1 = self.source
            p2 = self.target

            # type "moving" is never between different areas!
            if type(self.source) is Gate:
                # entry > positions
                return p2.distance_to_gate_in_m
                # p1 = self.target.nearest_gate_position #(gate_location=self.source.location)

            elif type(self.target) is Gate:
                # position > exit
                return p1.distance_to_gate_in_m
                # p2 = self.source.nearest_gate_position #(gate_location=self.target.location)

            else:
                # Manhattan distance
                distance_in_m = abs(p1.lane - p2.lane)*5 + abs(p1.row - p2.row)*20

                return distance_in_m

        else:
            return 0

    # Function: Compute duration in sec
    def compute_duration_in_sec(self, times, random_state, distribution):

        source = self.source.area.name if type(self.source) is Position else self.source.name
        target = self.target.area.name if type(self.target) is Position else self.target.name
        process_type = self.type

        try:
            self.data_availability_level = times[(source, target, process_type)]['data_availability_level']
        except:
            print('Key: ' + str((source, target, process_type))
                  + ' not found in times (instance_generator.Task.duration_in_sec()')

        if self.type == 'moving':
            # get speed (without distribution)
            speed_in_kmh = times[(source, target, process_type)]['mean']
            speed_in_ms = speed_in_kmh / 3.6

            # get delay in seconds based on an exponential distribution
            if distribution == 'Exp':
                mean = times[(source, target, 'moving_delay')]['mean']
                lambda_parameter = 1 / mean
                delay_in_sec = random_state.exponential(scale=1 / lambda_parameter)
            elif distribution == 'Normal':
                mean = times[(source, target, 'moving_delay')]['mean']
                delay_in_sec = max(1, random_state.normal(loc=mean, scale=mean / 2, size=1)[0])
            elif distribution == 'Average':
                delay_in_sec = times[(source, target, 'moving_delay')]['mean']
            else:
                print('Warning: Distribution=' + str(distribution) + ' not found in Task.compute_duration_in_sec()')
                delay_in_sec = 0

            time_in_sec = round(self.distance_in_m / speed_in_ms + delay_in_sec, 2)

            # print(str(self) + ': speed: ' + str(speed_in_kmh) +
            #       ', dist: ' + str(self.distance_in_m) +
            #       ' -> time in sec.: ' + str(time_in_sec) + ' (delay: ' + str(round(delay_in_sec, 2)) + ' sec.)'
            #       )

            self.duration_in_sec = round(max(1, time_in_sec), 2)
        else:
            # time in seconds based on an exponential distribution (with a mean)
            if distribution == 'Exp':
                lambda_parameter = 1 / times[(source, target, process_type)]['mean']
                time_in_sec = round(random_state.exponential(scale=1 / lambda_parameter), 2)

            elif distribution == 'Normal':
                mean = times[(source, target, process_type)]['mean']
                time_in_sec = max(1, random_state.normal(loc=mean, scale=mean / 2, size=1)[0])

            elif distribution == 'Average':
                time_in_sec = times[(source, target, process_type)]['mean']

            else:
                print('Warning: Distribution=' + str(distribution) + ' not found in Task.compute_duration_in_sec()')
                time_in_sec = 0

            # print(str(self) + ': time in sec.: ' + str(time_in_sec))

            self.duration_in_sec = round(max(1, time_in_sec), 2)

    # Function: Str
    def __str__(self):
        return str(self.type) + ' ' + str(self.source) + '->' + str(self.target)


# Class: Area
class Area:

    # Function: Init
    def __init__(self, name, gate_location, n_rows, n_lanes, n_decks):
        self.name = name
        self.n_rows = n_rows
        self.n_lanes = n_lanes
        self.n_decks = n_decks
        self.gate_location = gate_location
        self.positions = []
        self.initial_cargo = []
        self.pos_deck0_to_deck1 = None

        self.decks = [Deck(level=i, area=self) for i in range(self.n_decks)]

        # create entry/exit (gates)
        self.entry = Gate(area=self, location=self.gate_location, is_entry=True)
        self.exit = Gate(area=self, location=self.gate_location, is_exit=True)

    # Function: Str
    def __str__(self):
        return self.name


# Class: Deck
class Deck:

    # Function: Init
    def __init__(self, level, area):
        self.area = area
        self.level = level
        self.rows = {i + 1: [] for i in range(self.area.n_rows)}
        self.lanes = {i + 1: [] for i in range(self.area.n_lanes)}
        self.positions = []
        self.name = self.area.name + '-D' + str(self.level)

    # Function: Str
    def __str__(self):
        return self.name


# Class: Gate
class Gate:

    # Function: Init
    def __init__(self, area, location, is_entry=False, is_exit=False):
        self.area = area
        self.lane = None
        self.row = None
        self.is_entry = is_entry
        self.is_exit = is_exit
        self.location = location
        self.name = self.area.name
        self.name += '-Entry' if self.is_entry else '-Exit'

    # Function: Str
    def __str__(self):
        return self.name


# Class: Position
class Position:

    # Function: Init
    def __init__(self, area, lane, row, deck, is_for_selfdriving_cargo=False, is_for_towed_cargo=False, is_pathway=False,
                 is_barrier=False, is_elevator=False):
        self.area = area
        self.lane = lane
        self.row = row
        self.deck = deck

        self.is_for_selfdriving_cargo = is_for_selfdriving_cargo
        self.is_for_towed_cargo = is_for_towed_cargo
        self.is_pathway = is_pathway
        self.is_barrier = is_barrier
        self.is_elevator = is_elevator
        self.nearest_gate_position = None
        self.distance_to_gate_in_m = None

        self.neighbors = {}

        self.name = self.deck.name + '-L' + str(self.lane) + '-R' + str(self.row)

    # Function: Set nearest gate position
    def set_nearest_gate_position(self):

        for p in self.area.positions:
            if self.area.gate_location == 'bottom':
                # same lane, last row
                if p.lane == self.lane and p.row == self.area.n_rows:
                    self.nearest_gate_position = p
            elif self.area.gate_location == 'bottom-left':
                # first lane, last row
                if p.lane == 1 and p.row == self.area.n_rows:
                    self.nearest_gate_position = p
            elif self.area.gate_location == 'top-left':
                # first lane, first row
                if p.lane == 1 and p.row == 1:
                    self.nearest_gate_position = p
            elif self.area.gate_location == 'top-right':
                # last lane, first row
                if p.lane == self.area.n_lanes and p.row == 1:
                    self.nearest_gate_position = p
            elif self.area.gate_location == 'top':
                # same lane, first row
                if p.lane == self.lane and p.row == 1:
                    self.nearest_gate_position = p

        if self.nearest_gate_position is None:
            print('Rule ' + self.area.gate_location + ' not defined in Position.nearest_gate_position().')

    # Function: Set distance to gate in m
    def set_distance_to_gate_in_m(self):

        self.distance_to_gate_in_m = abs(self.lane - self.nearest_gate_position.lane) * 5 \
                                     + abs(self.row - self.nearest_gate_position.row) * 20

    # Function: Create neighbors
    def create_neighbors(self, positions):
        self.neighbors = {
            'tl': get_position_by_index(positions=positions, lane=self.lane - 1, row=self.row - 1, deck=self.deck),
            'tt': get_position_by_index(positions=positions, lane=self.lane, row=self.row - 1, deck=self.deck),
            'tr': get_position_by_index(positions=positions, lane=self.lane + 1, row=self.row - 1, deck=self.deck),
            'l': get_position_by_index(positions=positions, lane=self.lane - 1, row=self.row, deck=self.deck),
            'r': get_position_by_index(positions=positions, lane=self.lane + 1, row=self.row, deck=self.deck),
            'bl': get_position_by_index(positions=positions, lane=self.lane - 1, row=self.row + 1, deck=self.deck),
            'bb': get_position_by_index(positions=positions, lane=self.lane, row=self.row + 1, deck=self.deck),
            'br': get_position_by_index(positions=positions, lane=self.lane + 1, row=self.row + 1, deck=self.deck)
        }

    # Function: Str
    def __str__(self):
        return self.name


# Class: Cargo
class Cargo:

    # Function: Init
    def __init__(self, id, initial_position, arrival_time_in_sec, is_selfdriving):
        self.id = id
        self.initial_position = initial_position

        self.arrival_time_in_sec = arrival_time_in_sec
        self.is_selfdriving = is_selfdriving

    @property
    # Function: Is late
    def is_late(self):
        return True if self.arrival_time_in_sec > 0 else False

    # Function: Str
    def __str__(self):
        s = 'Cargo-'
        s += 'S_' if self.is_selfdriving else 'T_'
        return s + str(self.initial_position.area.name) + '-' + str(self.id)


# Class: Tug
class Tug:

    # Function: Init
    def __init__(self, id, initial_position):
        self.id = id
        self.initial_position = initial_position
        self.name = 't' + str(self.id)

    # Function: Str
    def __str__(self):
        return self.name


# Class: Instance
class Instance:

    # Function: Init
    def __init__(self, name, seed):
        # set seed & name
        self.seed = seed
        self.random_state = np.random.RandomState(seed=self.seed)

        self.name = name

        # get information for all instances
        df_all_instances = pd.read_excel('instance_generator_input.xlsx', sheet_name='instances')
        self.input = df_all_instances.set_index('name').to_dict('index')[name]

        self.ship_DC = self.input['ship_DC']
        self.ship_TC = self.input['ship_TC']
        self.terminal_DC = self.input['terminal_DC']
        self.terminal_TC = self.input['terminal_TC']

        if self.name == 'random':

            self.ship_DC = self.random_state.random_integers(
                low=self.ship_DC, 
                high=self.ship_TC
                )
            self.ship_TC = (self.input['ship_DC'] + self.input['ship_TC']) - self.ship_DC

            self.terminal_DC = self.ship_DC
            self.terminal_TC = self.ship_TC

        # create areas & cargo
        self.areas, self.cargo = self.get_areas_and_cargo_from_file()
        self.late_cargo = sorted([c for c in self.cargo if c.is_late],
                                 key=lambda x: x.arrival_time_in_sec)

        # position information
        self.create_neighbors_for_positions()
        self.ramp_positions_to_lower_deck = [p for p in self.areas['Ship'].positions if
                                                 p.deck.level == 1 and p.is_elevator]
        self.path_to_deck_0 = self.find_path_positions_to_deck_0()

        # create tugs
        self.tugs = self.create_tugs()

        # get information for the times
        self.times = self.get_times_from_file()

        # memory variables
        self.all_tasks = {}

    # Function: Find path positions to deck 0
    def find_path_positions_to_deck_0(self):
        upstream_locations = ['bl', 'bb', 'br']

        positions_to_deck_0 = [p for p in self.ramp_positions_to_lower_deck]
        check_pos = [p for p in self.ramp_positions_to_lower_deck]

        while len(check_pos) > 0:
            new_pos = check_pos[0]
            upstream_pos = [new_pos.neighbors[loc]
                            for loc in upstream_locations
                            if new_pos.neighbors[loc] is not None and
                            not new_pos.neighbors[loc].is_barrier]
            positions_to_deck_0.extend(upstream_pos)
            check_pos.extend(upstream_pos)
            check_pos = list(dict.fromkeys(check_pos[1:]))

        positions_to_deck_0 = list(dict.fromkeys(positions_to_deck_0))

        return positions_to_deck_0

    # Function: Create neighbors for positions
    def create_neighbors_for_positions(self):

        for positions in [self.areas['Ship'].positions, self.areas['Terminal'].positions]:
            for p in positions:
                p.create_neighbors(positions=positions)

    # Function: Create task
    def create_task(self, source, target, cargo, vehicle, type):

        if (source, target, cargo, vehicle, type) not in self.all_tasks:
            self.all_tasks[(source, target, cargo, vehicle, type)] = Task(
                source=source, target=target, cargo=cargo, vehicle=vehicle, type=type)

        return self.all_tasks[(source, target, cargo, vehicle, type)]
    
        # return Task(source=source, target=target, cargo=cargo, vehicle=vehicle, type=type)

    # Function: Get times from file
    def get_times_from_file(self):
        times_as_df = pd.read_excel('instance_generator_input.xlsx', sheet_name=self.input['process_times'])
        times = {
            (row1['source'], row1['target'], row1['process_type']): dict(
                mean=row1['mean'],
                data_availability_level=row1['data_availability_level']
            )
            for idx, row1 in times_as_df.iterrows()}

        return times

    # Function: Create areas depot and port
    def create_areas_depot_and_port(self):

        new_areas = {
            'Depot': Area(name='Depot',
                          n_rows=self.input['number_of_tugs'],
                          n_lanes=1,
                          n_decks=1,
                          gate_location='top'),

            'Port': Area(name='Port',
                         n_rows=1,
                         n_lanes=1,
                         n_decks=1,
                         gate_location='top')
        }

        # create empty positions for Depot & Port
        for name, area in new_areas.items():
            for deck in area.decks:
                for row in range(area.n_rows):
                    for lane in range(area.n_lanes):
                        pos = Position(lane=lane + 1, row=row + 1, deck=deck, area=area)
                        area.positions.append(pos)
                        deck.positions.append(pos)
                        deck.rows[pos.row].append(pos)
                        deck.lanes[pos.lane].append(pos)

            for pos in area.positions:
                pos.set_nearest_gate_position()
                pos.set_distance_to_gate_in_m()

        return new_areas

    # Function: Create terminal
    def create_terminal(self, layout_as_df, layout_parameters, areas):
        areas['Terminal'] = Area(name='Terminal',
                                 n_rows=layout_parameters['terminal_rows'],
                                 n_lanes=layout_parameters['terminal_lanes'],
                                 n_decks=1,
                                 gate_location='top-right') # top

        # create positions & cargo
        DC_terminal = []
        TC_terminal = []
        arrival_times = self.terminal_arrival_times_selfdriving_cargo()

        for deck in areas['Terminal'].decks:
            for row in range(areas['Terminal'].n_rows):
                for lane in range(areas['Terminal'].n_lanes):
                    value = layout_as_df.iloc[layout_parameters['first_row'] + row, layout_parameters['first_lane'] + lane]

                    is_for_selfdriving_cargo = True if value in ['A', 'AU', 'RM'] else False
                    is_for_towed_cargo = True if value in ['U', 'AU', 'RM'] else False
                    is_pathway = True if value not in ['A', 'U', 'AU', 'RM', 'X'] else False
                    is_barrier = True if value in ['X'] else False

                    pos = Position(lane=lane + 1, row=row + 1, deck=deck, area=areas['Terminal'],
                                   is_for_selfdriving_cargo=is_for_selfdriving_cargo,
                                   is_for_towed_cargo=is_for_towed_cargo,
                                   is_pathway=is_pathway,
                                   is_barrier=is_barrier)
                    areas['Terminal'].positions.append(pos)
                    deck.positions.append(pos)
                    deck.rows[pos.row].append(pos)
                    deck.lanes[pos.lane].append(pos)

                    # create cargo (if applicable)
                    if len(DC_terminal) < self.terminal_DC and is_for_selfdriving_cargo:
                        # self-driving cargo                        
                        DC_terminal.append(Cargo(id=len(DC_terminal) + 1,
                                                     initial_position=pos,
                                                     is_selfdriving=True,
                                                     arrival_time_in_sec=arrival_times[len(DC_terminal)]))

                    elif len(TC_terminal) < self.terminal_TC and is_for_towed_cargo:
                        # towed cargo                       
                        TC_terminal.append(Cargo(id=len(TC_terminal) + 1,
                                                     initial_position=pos,
                                                     is_selfdriving=False,
                                                     arrival_time_in_sec=0))

        areas['Terminal'].initial_cargo = DC_terminal + TC_terminal

        return DC_terminal + TC_terminal

    # Function: Create ship
    def create_ship(self, layout_as_df, layout_parameters, areas):
        areas['Ship'] = Area(name='Ship',
                             n_rows=layout_parameters['ship_rows'],
                             n_lanes=layout_parameters['ship_lanes'],
                             n_decks=3,
                             gate_location='bottom')

        # create positions
        for deck in areas['Ship'].decks:
            first_lane = 3 + areas['Terminal'].n_lanes + 3 + (deck.level * (areas['Ship'].n_lanes + 3))
            row_range = range(areas['Ship'].n_rows)
            row_range = reversed(row_range) if deck.level == 2 else row_range
            for row in row_range:
                for lane in range(areas['Ship'].n_lanes):
                    value = layout_as_df.iloc[layout_parameters['first_row'] + row, first_lane + lane]

                    is_for_selfdriving_cargo = True if value in ['A', 'AU', 'RM'] else False
                    is_for_towed_cargo = True if value in ['U', 'AU', 'RM'] else False
                    is_pathway = True if value not in ['A', 'U', 'AU', 'RM', 'X'] else False
                    is_barrier = True if value in ['X'] else False
                    is_elevator = True if value in ['RM', 'RL'] else False

                    pos = Position(lane=lane + 1, row=row + 1, deck=deck, area=areas['Ship'],
                                   is_for_selfdriving_cargo=is_for_selfdriving_cargo,
                                   is_for_towed_cargo=is_for_towed_cargo,
                                   is_pathway=is_pathway,
                                   is_barrier=is_barrier,
                                   is_elevator=is_elevator)
                    areas['Ship'].positions.append(pos)
                    deck.positions.append(pos)
                    deck.rows[pos.row].append(pos)
                    deck.lanes[pos.lane].append(pos)

                    if is_elevator:
                        areas['Ship'].pos_deck0_to_deck1 = pos

        # create cargo
        DC_ship = []
        TC_ship = []
        
        for id in range(1, self.ship_DC + 1):
            DC_ship.append(Cargo(id=id,
                                     initial_position=None,
                                     is_selfdriving=True,
                                     arrival_time_in_sec=0))
        
        for id in range(self.ship_DC, self.ship_DC + self.ship_TC):
            TC_ship.append(Cargo(id=id + 1,
                                     initial_position=None,
                                     is_selfdriving=False,
                                     arrival_time_in_sec=0))

        # assign positions
        areas['Ship'].initial_cargo = DC_ship + TC_ship
        self.random_state.shuffle(areas['Ship'].initial_cargo)
        
        c_idx = 0
        
        for pos in areas['Ship'].positions:
            if c_idx == len(areas['Ship'].initial_cargo):
                break

            if pos.is_for_selfdriving_cargo or pos.is_for_towed_cargo:
                areas['Ship'].initial_cargo[c_idx].initial_position = pos
                c_idx += 1

        return DC_ship + TC_ship

    # Function: Get areas and cargo from file
    def get_areas_and_cargo_from_file(self):
        # (Tug) Depot and Port
        areas = self.create_areas_depot_and_port()

        # Load Excel-File
        layout_as_df = pd.read_excel('instance_generator_input.xlsx', sheet_name=self.input['terminal_ship_layout'])
        layout_parameters = {row['parameter']: int(row['value']) for idx, row in layout_as_df.iterrows() if
                             row['parameter'] is not np.nan}
        layout_parameters['first_row'] = 10
        layout_parameters['first_lane'] = 3

        # Terminal (positions & cargo)
        cargo_terminal = self.create_terminal(layout_as_df=layout_as_df, layout_parameters=layout_parameters, areas=areas)

        # Ship (positions & cargo)
        cargo_ship = self.create_ship(layout_as_df=layout_as_df, layout_parameters=layout_parameters, areas=areas)

        # pre-calculate gate position and distance to gate
        for name, area in areas.items():
            for pos in area.positions:
                pos.set_nearest_gate_position()
                pos.set_distance_to_gate_in_m()

        return areas, cargo_terminal + cargo_ship

    # Function: Terminal arrival times selfdriving cargo
    def terminal_arrival_times_selfdriving_cargo(self):
        # creates a list of arrival times for the self-driving cargo at the terminal

        cargo_is_late = [self.random_state.choice([True, False], p=[self.input['terminal_late_DC_prob'],
                                                            1 - self.input['terminal_late_DC_prob']])
                         for c in range(self.terminal_DC)]

        arrival_time_in_sec = []

        for is_late in cargo_is_late:
            if is_late:
                arrival_time_in_sec.append(int(max(1,
                                                   round(
                                                       self.random_state.normal(loc=self.input['terminal_late_DC_avg_sec'],
                                                                        scale=self.input[
                                                                            'terminal_late_DC_std_sec']), 0)
                                                   )))
            else:
                arrival_time_in_sec.append(0)

        arrival_time_in_sec.sort()
        # print(arrival_time_in_sec)

        return arrival_time_in_sec

    # Function: Create tugs
    def create_tugs(self):
        return [Tug(id=tug_id + 1,
                    initial_position=self.areas['Depot'].positions[tug_id])
                for tug_id in range(self.input['number_of_tugs'])]

    # Function: Print stat
    def print_stat(self):
        print('Instance: ' + str(self.name))
        print(' Layout: ' + str(self.input['terminal_ship_layout']))
        print(' Times: ' + str(self.input['process_times']))
        print(' Areas:')

        for key, area in self.areas.items():
            print('  ' + str(key) + ': ', end='')
            pos_cargo = {}
            for pos in area.positions:
                if pos.value not in pos_cargo:
                    pos_cargo[pos.value] = dict(pos=1, DC=0, TC=0)
                else:
                    pos_cargo[pos.value]['pos'] += 1

                if pos.cargo is not None:
                    if pos.cargo.is_selfdriving:
                        pos_cargo[pos.value]['DC'] += 1
                    else:
                        pos_cargo[pos.value]['TC'] += 1

            print(pos_cargo)

    # Function: Plot stowage plan
    def plot_stowage_plan(self):
        import plotly.express as px

        df_dict = {
            'deck': [],
            'lane': [], 
            'row': [],
            'value': [],
            'marker_size': []
        }

        for c in self.cargo:
            if c.initial_position.area.name == 'Ship':
                df_dict['deck'].append(c.initial_position.deck.level)
                df_dict['lane'].append(c.initial_position.lane)
                df_dict['row'].append(c.initial_position.row)
                df_dict['value'].append('D' if c.is_selfdriving else 'T')
                df_dict['marker_size'].append(1)
        
        df = pd.DataFrame(df_dict)
        # print(df)

        fig = px.scatter(df, x='lane', y='row', color='value', facet_col='deck', size_max=20, size='marker_size', title=self.name)
        fig['layout']['yaxis']['autorange'] = 'reversed'

        fig.show()

    # Function: Str
    def __str__(self):
        return self.name + '_' + self.input['terminal_ship_layout'] + '_' + self.input['process_times']
