"""Define core simulation entities and solve realization runs for RoRo operations."""

import datetime
import instance_generator
import os
import pandas as pd
import statistics

# Define current time for real time conversion (arbitrary date, only time is relevant)
current_time = datetime.datetime(year=2024, month=4, day=1, hour=17, minute=00, second=00)


# Function: Get cargo
def get_cargo(cargo, model, area=None, target_status=None, is_selfdriving=None):
    return_cargo = []

    for get_c in cargo:
        add_c = True

        if area is not None:
            if model.pos_of_cargo[get_c].area != area:
                add_c = False

        if target_status is not None:
            if model.status[get_c] != target_status:
                add_c = False

        if is_selfdriving is not None:
            if get_c.is_selfdriving != is_selfdriving:
                add_c = False

        if add_c:
            return_cargo.append(get_c)

    return return_cargo


# Function: Get positions
def get_positions(area, status, target_status=None, valid_for_uCargo=None, valid_for_aCargo=None):
    return_pos = []

    for pos in area.positions:
        add_pos = True
        if target_status is not None:
            if status[pos] != target_status:
                add_pos = False

        if valid_for_uCargo is not None:
            if pos.is_for_towed_cargo != valid_for_uCargo:
                add_pos = False

        if valid_for_aCargo is not None:
            if pos.is_for_selfdriving_cargo != valid_for_aCargo:
                add_pos = False

        if add_pos:
            return_pos.append(pos)

    return return_pos


# Function: Get time
def get_time(date_time_object):
    return str(date_time_object.strftime("%H:%M:%S"))


# Function: Sec to real time
def sec_to_real_time(sec):
    return current_time + datetime.timedelta(days=0, seconds=sec)


# Function: Get position by index
def get_position_by_index(positions, lane, row, deck):
    for r_pos in positions:
        if r_pos.lane == lane and r_pos.row == row and r_pos.deck == deck:
            return r_pos

    return None


# Function: Pos qualifies for loading
def pos_qualifies_for_loading(combinations, model):
    for combination in combinations:
        if all(c_pos is None
               or c_pos.is_barrier
               or c_pos.is_pathway
               or model.status[c_pos] == 'taken (c)'
               for c_pos in combination):
            return True

    return False


# Function: Get decision with deck lane row rule
def get_decision_with_deck_lane_row_rule(remaining_decisions):

    # Select decision if multiple decisions exist
    if len(remaining_decisions) > 1:
        # print('multiple decisions: ' + str(len(decisions_with_max_count)))
        decision = None
        for d in remaining_decisions:
            if decision is None:
                decision = d
                continue
            # check ship-deck
            if decision.ship_position.deck.level > d.ship_position.deck.level:
                decision = d
                continue
            elif decision.ship_position.deck.level == d.ship_position.deck.level:
                # check ship-lane
                if decision.ship_position.lane > d.ship_position.lane:
                    decision = d
                    continue
                elif decision.ship_position.lane == d.ship_position.lane:
                    # check ship-row
                    if decision.ship_position.row > d.ship_position.row:
                        decision = d
                        continue
                    elif decision.ship_position.row == d.ship_position.row:
                        # check terminal-lane
                        if decision.terminal_position.lane > d.terminal_position.lane:
                            decision = d
                            continue
                        elif decision.terminal_position.lane == d.terminal_position.lane:
                            # check terminal-row
                            if decision.terminal_position.row > d.terminal_position.row:
                                decision = d
                                continue
                            elif decision.terminal_position.row == d.terminal_position.row:
                                # check vehicle-id (only tug-handled cargo)
                                if decision.vehicle.id > d.vehicle.id:
                                    decision = d
                                    continue
    else:
        decision = remaining_decisions[0]

    return decision


# Class: Tree
class Tree:

    # Function: Init
    def __init__(self, features, policy):
        self.features = features
        self.ordered_features = []
        self.update_ordered_features()

        self.policy = policy

        self.stat = dict()

    # Function: Update ordered features
    def update_ordered_features(self):
        self.ordered_features = [None for f in self.features if f.level is not None]

        for f in self.features:
            if f.level is not None:
                self.ordered_features[f.level] = f

    # Function: Levels as list
    def levels_as_list(self):
        return [f.level for f in self.features]

    # Function: Senses as list
    def senses_as_list(self):
        return [f.sense for f in self.features]

    # Function: Weights as list
    def weights_as_list(self):
        return [f.weight for f in self.features]

    # Function: Mutate two random levels
    def mutate_two_random_levels(self, random_state):

        f1, f2 = random_state.choice(self.features, 2, replace=False)

        f1.level, f2.level = f2.level, f1.level

        self.update_ordered_features()

    # Function: Swap feature
    def swap_feature(self, random_state, all_features):
        for f in all_features:
            f.level = None

            for f1 in self.features:
                if f.name == f1.name:
                    f.level = f1.level
                    break

        not_included_features = [f for f in all_features if f.level is None]

        f1 = random_state.choice(self.features, 1, replace=False)[0]
        f2 = random_state.choice(not_included_features, 1, replace=False)[0]
        f1.name = f2.name
        f1.sense = f2.sense

        self.update_ordered_features()

    # Function: Mutate one random sense
    def mutate_one_random_sense(self, random_state):
        f1 = random_state.choice(self.features)

        if f1.sense == 'yes':
            f1.sense = 'no'
        elif f1.sense == 'no':
            f1.sense = 'yes'
        elif f1.sense == 'min':
            f1.sense = 'max'
        elif f1.sense == 'max':
            f1.sense = 'min'
        else:
            print('Error: Sense ' + str(f1.sense) + ' not found!')

    # Function: Mutate random weight
    def mutate_random_weight(self, random_state):
        f1 = random_state.choice(self.features)

        if random_state.choice([True, False]):
            if f1.weight < 0.9:
                f1.weight += 0.2
            else:
                f1.weight -= 0.2
        else:
            if f1.weight > 0.1:
                f1.weight -= 0.2
            else:
                f1.weight += 0.2

        f1.weight = round(f1.weight, 1)

    # Function: Filter with hierarchy
    def filter_with_hierarchy(self, possible_decisions):
        remaining_decisions = possible_decisions

        for f in self.ordered_features:
            best_distance_in_m = 0
            best_taken_neighbors_in_pct = 0

            new_remaining_decisions = []

            if f.name == 'Total distance':
                if f.sense == 'min':
                    best_distance_in_m = min(d2.distance_in_m['total'] for d2 in remaining_decisions)
                else:
                    best_distance_in_m = max(d2.distance_in_m['total'] for d2 in remaining_decisions)
            elif f.name == 'Tug-to-cargo distance':
                if f.sense == 'min':
                    best_distance_in_m = min(d2.distance_in_m['vehicle_to_cargo'] for d2 in remaining_decisions)
                else:
                    best_distance_in_m = max(d2.distance_in_m['vehicle_to_cargo'] for d2 in remaining_decisions)
            elif f.name == 'Occupied adjacent positions':
                if f.sense == 'min':
                    best_taken_neighbors_in_pct = min(d2.full_neighbors_pct for d2 in remaining_decisions)
                else:
                    best_taken_neighbors_in_pct = max(d2.full_neighbors_pct for d2 in remaining_decisions)

            for d in remaining_decisions:
                if f.name == 'Loading':
                    if (f.sense == 'yes' and d.is_loading) or (f.sense == 'no' and not d.is_loading):
                        new_remaining_decisions.append(d)

                elif f.name == 'Unloading':
                    if (f.sense == 'yes' and not d.is_loading) or (f.sense == 'no' and d.is_loading):
                        new_remaining_decisions.append(d)

                elif f.name == 'Tug-handled cargo':
                    if (f.sense == 'yes' and d.vehicle is not None) or (f.sense == 'no' and d.vehicle is None):
                        new_remaining_decisions.append(d)

                elif f.name == 'Driver-handled cargo':
                    if (f.sense == 'yes' and d.vehicle is None) or (f.sense == 'no' and d.vehicle is not None):
                        new_remaining_decisions.append(d)

                elif f.name == 'Deck 0 (lower deck)':
                    if (f.sense == 'yes' and d.ship_position.deck.level == 0) or \
                            (f.sense == 'no' and d.ship_position.deck.level != 0):
                        new_remaining_decisions.append(d)

                elif f.name == 'Deck 1 (main deck)':
                    if (f.sense == 'yes' and d.ship_position.deck.level == 1) or \
                            (f.sense == 'no' and d.ship_position.deck.level != 1):
                        new_remaining_decisions.append(d)

                elif f.name == 'Deck 2 (upper deck)':
                    if (f.sense == 'yes' and d.ship_position.deck.level == 2) or \
                            (f.sense == 'no' and d.ship_position.deck.level != 2):
                        new_remaining_decisions.append(d)

                elif f.name == 'Double cycling ship':
                    if (f.sense == 'yes' and d.is_double_cycling_ship) or \
                            (f.sense == 'no' and not d.is_double_cycling_ship):
                        new_remaining_decisions.append(d)

                elif f.name == 'Double cycling terminal':
                    if (f.sense == 'yes' and d.is_double_cycling_terminal) or \
                            (f.sense == 'no' and not d.is_double_cycling_terminal):
                        new_remaining_decisions.append(d)

                elif f.name == 'Path to lower deck':
                    if (f.sense == 'yes' and d.on_path_to_deck_0) or (f.sense == 'no' and not d.on_path_to_deck_0):
                        new_remaining_decisions.append(d)

                elif f.name == 'Total distance':
                    if d.distance_in_m['total'] == best_distance_in_m:
                        new_remaining_decisions.append(d)

                elif f.name == 'Tug-to-cargo distance':
                    if d.distance_in_m['vehicle_to_cargo'] == best_distance_in_m:
                        new_remaining_decisions.append(d)

                elif f.name == 'Occupied adjacent positions':
                    if d.full_neighbors_pct == best_taken_neighbors_in_pct:
                        new_remaining_decisions.append(d)

                else:
                    print('Error: feature ' + str(f) + ' not found tree.filter_with_hierarchy().')

            if len(new_remaining_decisions) >= 1:
                remaining_decisions = new_remaining_decisions

            if len(new_remaining_decisions) == 1:
                break

        # if len(remaining_decisions) == len(possible_decisions):
        #     print('Analyze')

        return remaining_decisions

    # Function: Filter with feature weights
    def filter_with_feature_weights(self, possible_decisions):
        best_total_distance_in_m = 0
        best_tug_to_cargo_distance_in_m = 0
        best_taken_neighbors_in_pct = 0

        for f in self.features:
            if f.weight > 0:
                if f.name == 'Total distance':
                    if f.sense == 'min':
                        best_total_distance_in_m = min(d2.distance_in_m['total'] for d2 in possible_decisions)
                    else:
                        best_total_distance_in_m = max(d2.distance_in_m['total'] for d2 in possible_decisions)
                elif f.name == 'Tug-to-cargo distance':
                    if f.sense == 'min':
                        best_tug_to_cargo_distance_in_m = min(d2.distance_in_m['vehicle_to_cargo'] for d2 in possible_decisions)
                    else:
                        best_tug_to_cargo_distance_in_m = max(d2.distance_in_m['vehicle_to_cargo'] for d2 in possible_decisions)
                elif f.name == 'Occupied adjacent positions':
                    if f.sense == 'min':
                        best_taken_neighbors_in_pct = min(d2.full_neighbors_pct for d2 in possible_decisions)
                    else:
                        best_taken_neighbors_in_pct = max(d2.full_neighbors_pct for d2 in possible_decisions)

        remaining_decisions = []
        best_score = 0
        for d in possible_decisions:
            if len(remaining_decisions) == 0:
                remaining_decisions.append(d)
                best_score = d.score(features=self.features,
                                     best_total_distance_in_m=best_total_distance_in_m,
                                     best_tug_to_cargo_distance_in_m=best_tug_to_cargo_distance_in_m,
                                     best_taken_neighbors_in_pct=best_taken_neighbors_in_pct)
                continue

            new_score = d.score(features=self.features,
                                best_total_distance_in_m=best_total_distance_in_m,
                                best_tug_to_cargo_distance_in_m=best_tug_to_cargo_distance_in_m,
                                best_taken_neighbors_in_pct=best_taken_neighbors_in_pct)

            if new_score > best_score:
                remaining_decisions = [d]
                best_score = new_score

            elif new_score == best_score:
                remaining_decisions.append(d)

        return remaining_decisions

    # Function: Cart duration in min
    def cart_duration_in_min(self, CART_model, all_features):

        for f in all_features:
            f.level = None

            for f1 in self.features:
                if f.name == f1.name:
                    f.level = f1.level
                    break
        
        feature_vector = [f.level for f in all_features]

        cart_prediction_duration_in_min = CART_model.predict([feature_vector])

        # print(feature_vector)        
        # print('CART prediction: ' + str(cart_prediction_duration_in_min))

        return cart_prediction_duration_in_min[0]

    # Function: Str
    def __str__(self):
        # if 'Feature Counting' in self.policy:
        #     return str([str(f.name + ' (' + str(f.weight) + ')') for f in self.features if f.weight > 0])
        # else:
        #     return str([str(f.name + ' (' + str(f.level) + ')') for f in self.ordered_features])
        if 'Feature Counting' in self.policy:
            return str([str(f.name) for f in self.features if f.weight > 0])
        else:
            return str([str(f.name) for f in self.ordered_features])


# Class: Feature
class Feature:

    # Function: Init
    def __init__(self, name, sense, level=None, weight=None):
        self.name = name

        self.level = level
        self.sense = sense
        self.weight = weight

    # Function: Str
    def __str__(self):
        return self.name + ' (' + str(self.level) + ')'
        # return self.name + ' (' + str(self.level) + ',' + str(self.sense) + ')'


# Class: Decision
class Decision:

    # Function: Init
    def __init__(self, epoch, time_start_in_sec, vehicle, cargo, target, is_loading, model):
        self.epoch = epoch
        self.time_start_in_sec = time_start_in_sec
        self.time_end_in_sec = time_start_in_sec  # will be updated later

        self.is_loading = is_loading
        self.vehicle = vehicle
        self.cargo = cargo
        self.target = target

        # derive additional positions
        self.source = model.pos_of_cargo[self.cargo]
        self.ship_position = self.target if self.is_loading else model.pos_of_cargo[self.cargo]
        self.terminal_position = self.get_terminal_position()

        # create and compute decision's information
        self.tasks = self.create_tasks(model=model, instance=model.instance)
        self.distance_in_m = self.compute_distance_in_m()
        self.full_neighbors_pct = self.compute_full_neighbors_pct(model=model)
        self.is_double_cycling_terminal = False
        self.is_double_cycling_ship = False
        self.update_double_cycling(model=model)
        self.on_path_to_deck_0 = True if self.ship_position in model.path_to_deck_0 else False

        # variables used in other parts of the program
        self.is_completed = False
        self.busy_on_ship_deck = None
        self.postpone_probability = 0
        self.total_decisions = 0
        self.pct_filtered_decisions = 0

    # Function: Compute full neighbors pct
    def compute_full_neighbors_pct(self, model):
        ship_position_neighbors = list(self.ship_position.neighbors.values())

        full_neighbors_pct = round(sum(1 for pos in ship_position_neighbors
                                            if pos is not None and model.status[pos] == 'taken') /
                                        sum(1 for pos in ship_position_neighbors
                                            if pos is not None),
                                        4)

        return full_neighbors_pct

    # Function: Update double cycling
    def update_double_cycling(self, model):
        if self.vehicle is not None:
            if self.cargo is not None:
                if model.pos_of_tug[self.vehicle].area == model.pos_of_cargo[self.cargo].area:
                    if model.pos_of_tug[self.vehicle].area.name == 'Ship':
                        self.is_double_cycling_ship = True
                    else:
                        self.is_double_cycling_terminal = False

    # Function: Get terminal position
    def get_terminal_position(self):
        if self.is_loading:
            return self.source
        else:
            if isinstance(self.target, instance_generator.Position):
                return self.target

        return None

    # Function: Create tasks
    def create_tasks(self, model, instance):
        tasks = []

        # case 1: with tug, with cargo (remark: towed/unaccompanied cargo)
        # case 2: with tug, without cargo
        # case 3: no tug, with cargo (remark: selfdriving/accompanied cargo)
        # case 4: no tug, no cargo (remark: not applicable)
        if self.vehicle is not None and self.cargo is not None:
            # case 1
            # handling source
            tasks.extend(
                [instance.create_task(source=model.pos_of_tug[self.vehicle], target=model.pos_of_tug[self.vehicle],
                                           cargo=None, vehicle=self.vehicle, type='handling tug-only source')])

            # tug position ->  cargo position
            tasks.extend(
                self.get_tasks_source_target(source=model.pos_of_tug[self.vehicle], target=model.pos_of_cargo[self.cargo],
                                             vehicle=self.vehicle, cargo=None, instance=instance)
            )

            # coupling
            tasks.extend(
                [instance.create_task(source=model.pos_of_cargo[self.cargo], target=model.pos_of_cargo[self.cargo],
                                           cargo=self.cargo, vehicle=self.vehicle, type='coupling')])

            # cargo position -> target
            tasks.extend(self.get_tasks_source_target(source=model.pos_of_cargo[self.cargo], target=self.target,
                                                           vehicle=self.vehicle, cargo=self.cargo, instance=instance)
                              )

            # decoupling
            tasks.extend([instance.create_task(source=self.target, target=self.target,
                                                         cargo=self.cargo, vehicle=self.vehicle, type='decoupling')])

        elif self.vehicle is not None and self.cargo is None:
            # case 2
            # handling source
            tasks.extend(
                [instance.create_task(source=model.pos_of_tug[self.vehicle], target=model.pos_of_tug[self.vehicle],
                                           cargo=None, vehicle=self.vehicle, type='handling tug-only source')])

            # tug position ->  target
            tasks.extend(self.get_tasks_source_target(source=model.pos_of_tug[self.vehicle], target=self.target,
                                                           vehicle=self.vehicle, cargo=self.cargo, instance=instance)
                              )

            # handling target
            tasks.extend([instance.create_task(source=self.target, target=self.target,
                                                         cargo=None, vehicle=self.vehicle, type='handling tug-only target')])

        elif self.vehicle is None and self.cargo is not None:
            # case 3
            # handling source
            tasks.extend(
                [instance.create_task(source=model.pos_of_cargo[self.cargo], target=model.pos_of_cargo[self.cargo],
                                           cargo=self.cargo, vehicle=self.vehicle, type='handling aCargo source')])

            # cargo position ->  target
            tasks.extend(self.get_tasks_source_target(source=model.pos_of_cargo[self.cargo], target=self.target,
                                                           cargo=self.cargo, vehicle=self.vehicle, instance=instance)
                              )

            # handling target
            tasks.extend([instance.create_task(source=self.target, target=self.target,
                                                         cargo=self.cargo, vehicle=self.vehicle, type='handling aCargo target')])

        else:
            # case 4
            print('Error: case not found in Aggregated_Task')

        return tasks

    # Function: Get tasks source target
    def get_tasks_source_target(self, instance, source, target, cargo, vehicle):

        if source.area == target.area:
            return [instance.create_task(source=source, target=target, cargo=cargo, vehicle=vehicle, type='moving')]

        elif source.name == 'Port-Entry':
            return [instance.create_task(source=source, target=target.area.entry, cargo=cargo, vehicle=vehicle, type='area change'),
                    instance.create_task(source=target.area.entry, target=target.area.entry, cargo=cargo, vehicle=vehicle,
                         type='gate operation'),
                    instance.create_task(source=target.area.entry, target=target, cargo=cargo, vehicle=vehicle, type='moving')
                    ]
        elif target.name == 'Port-Exit':
            return [
                instance.create_task(source=source, target=source.area.exit, cargo=cargo, vehicle=vehicle, type='moving'),
                instance.create_task(source=source.area.exit, target=source.area.exit, cargo=cargo, vehicle=vehicle,
                     type='gate operation'),
                instance.create_task(source=source.area.exit, target=target, cargo=cargo, vehicle=vehicle, type='area change')
                # self.instance.create_task(source=target, target=target, cargo=cargo, vehicle=vehicle, type='handling aCargo target',
                #      times=times)
            ]
        else:
            if source.area.name == 'Ship' and source.deck.level == 0:
                return [instance.create_task(source=source, target=source.area.pos_deck0_to_deck1,
                             cargo=cargo, vehicle=vehicle, type='moving'),
                        instance.create_task(source=source.area.pos_deck0_to_deck1, target=source.area.exit,
                             cargo=cargo, vehicle=vehicle, type='moving'),
                        instance.create_task(source=source.area.exit, target=source.area.exit,
                            cargo=cargo, vehicle=vehicle, type='gate operation'),
                        instance.create_task(source=source.area.exit, target=target.area.entry,
                             cargo=cargo, vehicle=vehicle, type='area change'),
                        instance.create_task(source=target.area.entry, target=target.area.entry,
                             cargo=cargo, vehicle=vehicle, type='gate operation'),
                        instance.create_task(source=target.area.entry, target=target,
                             cargo=cargo, vehicle=vehicle, type='moving')
                        ]
            elif target.area.name == 'Ship' and target.deck.level == 0:
                return [
                    instance.create_task(source=source, target=source.area.exit,
                         cargo=cargo, vehicle=vehicle, type='moving'),
                    instance.create_task(source=source.area.exit, target=source.area.exit,
                         cargo=cargo, vehicle=vehicle, type='gate operation'),
                    instance.create_task(source=source.area.exit, target=target.area.entry,
                         cargo=cargo, vehicle=vehicle, type='area change'),
                    instance.create_task(source=target.area.entry, target=target.area.entry,
                         cargo=cargo, vehicle=vehicle, type='gate operation'),
                    instance.create_task(source=target.area.entry, target=target.area.pos_deck0_to_deck1,
                         cargo=cargo, vehicle=vehicle, type='moving'),
                    instance.create_task(source=target.area.pos_deck0_to_deck1, target=target,
                         cargo=cargo, vehicle=vehicle, type='moving')
                ]
            else:
                return [
                    instance.create_task(source=source, target=source.area.exit,
                         cargo=cargo, vehicle=vehicle, type='moving'),
                    instance.create_task(source=source.area.exit, target=source.area.exit,
                         cargo=cargo, vehicle=vehicle, type='gate operation'),
                    instance.create_task(source=source.area.exit, target=target.area.entry,
                         cargo=cargo, vehicle=vehicle, type='area change'),
                    instance.create_task(source=target.area.entry, target=target.area.entry,
                         cargo=cargo, vehicle=vehicle, type='gate operation'),
                    instance.create_task(source=target.area.entry, target=target,
                         cargo=cargo, vehicle=vehicle, type='moving')
                ]

    # Function: Compute distance in m
    def compute_distance_in_m(self):
        distance_in_m = {'vehicle_to_cargo': 0,
                         'cargo_to_target': 0,
                         'total': 0}

        for task in self.tasks:
            if task.cargo is None:
                distance_in_m['vehicle_to_cargo'] += task.distance_in_m
            else:
                distance_in_m['cargo_to_target'] += task.distance_in_m

            distance_in_m['total'] += task.distance_in_m

        return distance_in_m

    # Function: Update model
    def update_model(self, model):
        # set epoch
        self.epoch = model.e

        # update which ship deck is 'busy' by the decision
        if self.target.area.name == 'Ship':
            # loading
            self.busy_on_ship_deck = self.target.deck
            if self.is_double_cycling_ship:
                model.double_cycling_ship_positions.append(self.target)

        if self.cargo is not None:

            if model.pos_of_cargo[self.cargo].area.name == 'Ship':
                # unloading
                self.busy_on_ship_deck = model.pos_of_cargo[self.cargo].deck
                if self.is_double_cycling_ship:
                    model.double_cycling_ship_positions.append(model.pos_of_cargo[self.cargo])

        # update initial status
        if self.cargo is not None:
            model.status[self.cargo] = 'reserved'
            if isinstance(model.pos_of_cargo[self.cargo], instance_generator.Position):
                model.status[model.pos_of_cargo[self.cargo]] = 'reserved'

                if model.composition.plot_animation:
                    if self.vehicle is None:
                        model.history[model.pos_of_cargo[self.cargo]] += '<br>' + get_time(
                        self.real_time_start) + ' reserved (self-driving)'

                    else:
                        model.history[model.pos_of_cargo[self.cargo]] += '<br>' \
                                                                                      + get_time(self.real_time_start) \
                                                                                      + ' reserved' \
                                                                                      + ': tug=' + str(self.vehicle) \
                                                                                      + ' from ' + model.pos_of_tug[self.vehicle].name

        if isinstance(self.target, instance_generator.Position):
            model.status[self.target] = 'reserved'

            if model.composition.plot_animation:
                if self.vehicle is None:
                    model.history[self.target] += '<br>' \
                                                                  + get_time(self.real_time_start) \
                                                                  + ' reserved (self-driving)'
                else:
                    model.history[self.target] += '<br>' \
                                                                  + get_time(self.real_time_start) \
                                                                  + ' reserved' \
                                                                  + ': tug=' + str(self.vehicle) \
                                                                  + ' from ' + model.pos_of_tug[self.vehicle].name

        if self.vehicle is not None:
            model.status[self.vehicle] = 'busy'

        # create events from tasks
        t_running = self.time_start_in_sec
        postponed_events = []

        # analyzing_pos = 'Ship-D1-L7-R12'
        # if str(self.source) == analyzing_pos:
        #     print('t=' + str(model.t))
        #     print(self)

        for task in self.tasks:
            task.compute_duration_in_sec(times=model.instance.times,
                                         random_state=model.composition.rng,
                                         distribution=model.composition.distribution_function_times)

            # if str(self.source) == analyzing_pos:
            #     print(' ' + str(task) + ' ' + str(task.duration_in_sec))

            new_event = CompletedEvent(time_start_in_sec=t_running, task=task, decision=self)

            t_running += task.duration_in_sec

            if new_event.task.data_availability_level <= model.composition.data_availability_level or new_event == \
                    self.tasks[-1]:
                new_event.postponed_events = postponed_events
                if new_event.time_end_in_sec in model.events_at_time:
                    model.events_at_time[new_event.time_end_in_sec].append(new_event)
                else:
                    model.events_at_time[new_event.time_end_in_sec] = [new_event]

                model.all_t_events_in_sec.add(new_event.time_end_in_sec)

                postponed_events = []
            else:
                postponed_events.append(new_event)

        self.time_end_in_sec = t_running

        if self.time_end_in_sec > model.t_last_event_in_sec:
            model.t_last_event_in_sec = self.time_end_in_sec

        # if str(self.source) == analyzing_pos:
        #     print(self)

        # if model.t_last_event_in_sec < 500:
        #     print(str(model.t_last_event_in_sec))

    # Function: Score
    def score(self, features, best_total_distance_in_m, best_tug_to_cargo_distance_in_m, best_taken_neighbors_in_pct):
        score = 0
        for f in features:
            if f.weight > 0:
                if f.name == 'Loading':
                    if (f.sense == 'yes' and self.is_loading) or (f.sense == 'no' and not self.is_loading):
                        score += f.weight

                elif f.name == 'Unloading':
                    if (f.sense == 'yes' and not self.is_loading) or (f.sense == 'no' and self.is_loading):
                        score += f.weight

                elif f.name == 'Tug-handled cargo':
                    if (f.sense == 'yes' and self.vehicle is not None) or (f.sense == 'no' and self.vehicle is None):
                        score += f.weight

                elif f.name == 'Driver-handled cargo':
                    if (f.sense == 'yes' and self.vehicle is None) or (f.sense == 'no' and self.vehicle is not None):
                        score += f.weight

                elif f.name == 'Deck 0 (lower deck)':
                    if (f.sense == 'yes' and self.ship_position.deck.level == 0) or \
                            (f.sense == 'no' and self.ship_position.deck.level != 0):
                        score += f.weight

                elif f.name == 'Deck 1 (main deck)':
                    if (f.sense == 'yes' and self.ship_position.deck.level == 1) or \
                            (f.sense == 'no' and self.ship_position.deck.level != 1):
                        score += f.weight

                elif f.name == 'Deck 2 (upper deck)':
                    if (f.sense == 'yes' and self.ship_position.deck.level == 2) or \
                            (f.sense == 'no' and self.ship_position.deck.level != 2):
                        score += f.weight

                elif f.name == 'Double cycling ship':
                    if (f.sense == 'yes' and self.is_double_cycling_ship) or \
                            (f.sense == 'no' and not self.is_double_cycling_ship):
                        score += f.weight

                elif f.name == 'Double cycling terminal':
                    if (f.sense == 'yes' and self.is_double_cycling_terminal) or \
                            (f.sense == 'no' and not self.is_double_cycling_terminal):
                        score += f.weight

                elif f.name == 'Path to lower deck':
                    if (f.sense == 'yes' and self.on_path_to_deck_0) or (f.sense == 'no' and not self.on_path_to_deck_0):
                        score += f.weight

                elif f.name == 'Total distance':
                    if (f.sense == 'yes' and self.distance_in_m['total'] == best_total_distance_in_m) or \
                            (f.sense == 'no' and self.distance_in_m['total'] != best_total_distance_in_m):
                        score += f.weight

                elif f.name == 'Tug-to-cargo distance':
                    if (f.sense == 'yes' and self.distance_in_m['vehicle_to_cargo'] == best_tug_to_cargo_distance_in_m) or \
                            (f.sense == 'no' and self.distance_in_m['vehicle_to_cargo'] != best_tug_to_cargo_distance_in_m):
                        score += f.weight

                elif f.name == 'Occupied adjacent positions':
                    if (f.sense == 'yes' and self.full_neighbors_pct == best_taken_neighbors_in_pct) or \
                            (f.sense == 'no' and self.full_neighbors_pct != best_taken_neighbors_in_pct):
                        score += f.weight

                else:
                    print('Error: feature ' + str(f) + ' not found decision.score().')

        return score

    # Function: Str
    def __str__(self):
        return_str = 'source (cargo pos): ' + str(self.source)
        return_str += ', tug: '
        return_str += ' ' + str(self.vehicle)
        return_str += ', target: ' + self.target.name
        return_str += ', time_end=' + str(self.time_end_in_sec)

        return return_str

    @property
    # Function: Real time start
    def real_time_start(self):
        return current_time + datetime.timedelta(days=0, seconds=self.time_start_in_sec)

    @property
    # Function: Real time end
    def real_time_end(self):
        return current_time + datetime.timedelta(days=0, seconds=self.time_end_in_sec)


# Class: Completed Event
class CompletedEvent:

    # Function: Init
    def __init__(self, time_start_in_sec, task, decision):

        self.time_start_in_sec = time_start_in_sec
        self.task = task
        self.decision = decision
        self.time_end_in_sec = round(self.time_start_in_sec + self.task.duration_in_sec, 2)
        self.postponed_events = []

    # Function: Consider impact
    def consider_impact(self, model):
        # consider impact of (potentially) postponed events
        for pe in self.postponed_events:
            pe.consider_impact(model=model)

        # helping variables
        status = model.status
        history = model.history
        real_time = get_time(model.real_time)

        # if str(self.task.source) == 'Terminal-D0-L28-R3':
        #     print(self)
        #     tmp_pos = self.task.source
        #     print('position: ' + str(tmp_pos))
        #     print(' pos-status: ' + str(status[tmp_pos]))
        #     print(' cargo: ' + str(model.cargo_of_pos[tmp_pos]) + ', late: ' + str(model.cargo_of_pos[tmp_pos].arrival_time_in_sec))
        #     print(' cargo-status: ' + str(status[model.cargo_of_pos[tmp_pos]]))

        # status
        if self.task.type in ['decoupling']:
            status[self.task.vehicle] = 'available'
            status[self.task.cargo] = 'completed'
            status[self.task.target] = 'taken (c)'

            self.decision.busy_on_ship_deck = None
            self.decision.is_completed = True
            model.cargo_of_pos[self.task.target] = self.task.cargo

            model.pos_of_cargo[self.task.cargo] = self.task.target

            if model.composition.plot_animation:
                history[self.task.target] += '<br>' + real_time + ' taken' \
                                             + ': tug=' + str(self.task.vehicle) \
                                             + ', cargo=' + str(self.task.cargo)

        elif self.task.type in ['coupling']:
            status[self.task.cargo] = 'busy'
            status[self.task.source] = 'empty'
            model.cargo_of_pos[self.task.source] = None

            if model.composition.plot_animation:
                history[self.task.source] += '<br>' + real_time + ' empty' \
                                             + ': tug=' + str(self.task.vehicle)

        elif self.task.type in ['handling tug-only target']:
            status[self.task.vehicle] = 'available'
            self.decision.busy_on_ship_deck = None
            self.decision.is_completed = True

        elif self.task.type in ['handling aCargo target']:
            self.decision.busy_on_ship_deck = None
            self.decision.is_completed = True

            if self.task.cargo.arrival_time_in_sec > 0 and isinstance(self.task.target,
                                                                      instance_generator.Position) and self.task.target.area.name == 'Terminal':
                # late cargo
                status[self.task.cargo] = 'available'
                status[self.task.target] = 'taken'
            else:
                status[self.task.cargo] = 'completed'
                status[self.task.target] = 'taken (c)'

            if isinstance(self.task.target, instance_generator.Position):
                model.cargo_of_pos[self.task.target]= self.task.cargo
                model.pos_of_cargo[self.task.cargo] = self.task.target

                if model.composition.plot_animation:
                    history[self.task.target] += '<br>' + real_time + ' taken' \
                                                 + ': tug=' + str(self.task.vehicle) \
                                                 + ', cargo=' + str(self.task.cargo)

        elif self.task.type in ['handling aCargo source'] and isinstance(self.task.source, instance_generator.Position):
            status[self.task.source] = 'empty'
            model.cargo_of_pos[self.task.source] = None
            if model.composition.plot_animation:
                history[self.task.source] += '<br>' + real_time + ' empty' \
                                             + ': tug=' + str(self.task.vehicle)

        # position vehicle
        if self.task.vehicle is not None:
            model.pos_of_tug[self.task.vehicle] = self.task.target

        # update deck utilization
        if self.task.type in ['gate_operation']:
            if self.task.source.name == 'Ship-Exit' and self.task.target.name == 'Ship-Exit':
                self.decision.busy_on_ship_deck = None

        # position cargo
        if self.task.cargo is not None:
            if status[self.task.cargo] == 'busy':
                model.pos_of_cargo[self.task.cargo] = self.task.target

    # Function: Str
    def __str__(self):
        return 't' + str(self.time_start_in_sec) + ': ' + str(self.task.type)

    @property
    # Function: Real time start
    def real_time_start(self):
        return current_time + datetime.timedelta(days=0, seconds=self.time_start_in_sec)

    @property
    # Function: Real time end
    def real_time_end(self):
        return current_time + datetime.timedelta(days=0, seconds=self.time_end_in_sec)


# Class: Realization
class Realization:

    # Function: Init
    def __init__(self, id, composition, instance, tree=None):

        self.id = id
        self.composition = composition
        self.tree = tree

        # information from instance
        self.instance = instance
        self.areas = self.instance.areas
        self.Ship = self.areas['Ship']
        self.Terminal = self.areas['Terminal']
        self.Tugs = self.instance.tugs
        self.Cargo = self.instance.cargo
        self.late_cargo = self.instance.late_cargo
        self.path_to_deck_0 = self.instance.path_to_deck_0

        ########### MODEL
        self.policy_completed = False
        self.unloading_completed = False
        self.ramp_to_lower_deck_had_been_opened = False
        self.unloading_completion_time = None

        # default values
        self.t = 0  # time in seconds
        self.e = 0  # decision epoch

        self.status = {}
        self.pos_of_cargo = {}
        self.cargo_of_pos = {}
        self.pos_of_tug = {}

        for p in self.Ship.positions + self.Terminal.positions:
            self.cargo_of_pos[p] = None
            self.status[p] = 'pathway' if p.is_pathway else 'barrier' if p.is_barrier else 'empty'

        for c in self.Cargo:
            self.cargo_of_pos[c.initial_position] = c
            self.pos_of_cargo[c] = c.initial_position
            self.status[c.initial_position] = 'taken'

        self.history = {}
        if self.composition.plot_animation:
            self.history = {
                p: '<br>' + get_time(self.real_time) + ' (initial): ' + str(self.cargo_of_pos[p]) if self.cargo_of_pos[
                                                                                                         p] is not None else ' '
                for p
                in self.Ship.positions + self.Terminal.positions}

        self.double_cycling_ship_positions = []

        for tug in self.Tugs:
            self.status[tug] = 'available'
            self.pos_of_tug[tug] = tug.initial_position
        for cargo in self.Cargo:
            self.status[cargo] = 'available' if cargo.arrival_time_in_sec == 0 else 'late'

        self.stored_status = []
        self.store_status()

        self.t = 1
        self.e = 1

        self.events_at_time = dict()
        self.all_t_events_in_sec = set()
        self.t_last_event_in_sec = 0
        self.list_of_decisions = []
        self.count_skipped_decisions = 0
		
    # Function: Solve
    def solve(self, plot=False, save=False, print_steps=False, print_high_level_steps=False):
        if print_steps or print_high_level_steps:
            print('')
            print(self.stat())
            print(' solve via ' + str(self.composition.policy))

        # initialize model
        if print_steps:
            # all epochs
            print('  epoch ' + str(self.e) + ' (' + get_time(self.real_time) + '): ' + self.stat_current_state)

        output_str = ''

        while not self.policy_completed:
            if print_steps:
                output_str = '  epoch ' + str(self.e) + ' (' + get_time(self.real_time) + '): decision: [t=' + str(self.t) + ': '

            # find a decision
            decision, all_possible_decisions = self.find_decision()
            if print_steps:
                output_str += str(decision) + '], # potential decisions: ' + str(len(all_possible_decisions))

            # transit to next state
            self.transition(decision=decision, print_steps=print_steps,
                         print_high_level_steps=print_high_level_steps,
                         all_possible_decisions=all_possible_decisions)
            if print_steps:
                output_str += ', # future epochs: ' + str(sum(1 for e in self.events_at_time if e > self.t))

            if decision is not None:
                if print_steps:
                    print(output_str)
                    print('  * deck utilization: ' + str({deck.level: value
                                                          for deck, value in self.active_decisions_per_deck().items()}))
                    # print('   ' + self.stat_current_state)

            if print_steps or print_high_level_steps:
                if self.e % 500 == 0:
                    print('  epoch ' + str(self.e) + ' (' + get_time(self.real_time) + '): ' + self.stat_current_state)

            # increase decision epoch counter
            self.e += 1

        self.store_status()

        if print_steps or print_high_level_steps:
            print('  epoch (final) ' + str(self.e) + ' (' + get_time(self.real_time) + '): ' + self.stat_current_state)
            print('  * deck utilization: ' + str({deck.level: value
                                                  for deck, value in self.active_decisions_per_deck().items()}))
            print('  * number of skipped decisions: ' + str(self.count_skipped_decisions))

        # self.save_kpis()

        if save or plot:
            self.save()

        if plot:
            self.plot(title=self.composition.name
                            + ' completion time: '
                            + self.unloading_completion_time.strftime("%H:%M:%S") + ' (unloading), '
                            + self.real_time.strftime("%H:%M:%S") + ' (loading)')

        if print_high_level_steps or print_steps:
            print(' -> completion time: ' + get_time(self.real_time))

    # Function: Save
    def save(self):
        print('')
        print('   save model...', end='')

        # # model as Pickle
        # print(' realization ', end='')
        # pickle.dump(self, open(self.folder_results + 'realization.pickle', 'wb'))

        # decisions
        print(' decisions ', end='')
        self.df_decisions().to_excel(self.folder_results+ 'decisions.xlsx', index=False)

        # events
        print(' events ', end='')
        self.df_events().to_excel(self.folder_results + 'events.xlsx', index=False)

        # status
        print(' status ', end='')
        self.df_status().to_excel(self.folder_results + 'status.xlsx', index=False)

        print('completed')

    # Function: Add to results data
    def add_to_results_data(self, results_data):

        kpi_dict = {
            'run_date_time': datetime.datetime.now(),
            'policy': self.composition.policy,
            'decision_policy': self.composition.decision_policy,
            'learning_policy': self.composition.learning_policy,
            'instance': self.instance.name,
            'instance_seed': self.instance.seed,
            'data_availability_level': self.composition.data_availability_level_text,
            'id_realization': self.id,
            'distribution_function_times': self.composition.distribution_function_times,
            'number_of_features': self.composition.number_of_features,
            'batch': self.composition.batch,
            'completion_time': self.real_time,
            'duration_in_min': (self.real_time - current_time).total_seconds() / 60,
            # 'duration_in_hours': (self.real_time - current_time).total_seconds() / 3600,
            # 'duration_in_sec': (self.real_time - current_time).total_seconds(),
            'unloading_completion_time': self.unloading_completion_time,
            'unloading_duration_in_min': (self.unloading_completion_time - current_time).total_seconds() / 60,
            # 'unloading_duration_in_hours': (self.unloading_completion_time - current_time).total_seconds() / 3600,
            'last_epoch': self.e,
            'pct_filtered_decisions': statistics.mean([d.pct_filtered_decisions for d in self.list_of_decisions])
        }
        kpi_dict['loading_duration_in_min'] = kpi_dict['duration_in_min'] - kpi_dict['unloading_duration_in_min']
        # kpi_dict['loading_duration_in_hours'] = kpi_dict['duration_in_hours'] - kpi_dict['unloading_duration_in_hours']

        for key, value in kpi_dict.items():
            results_data[key] = results_data[key] + [value] if key in results_data else [value]

    # Function: Plot
    def plot(self, title):
        # Create animation of the loading/unloading process (plotly)

        print('plotting...', end='')

        df_status = pd.read_excel(self.folder_results + 'status.xlsx')
        df_status = df_status.loc[df_status['area'].isin(['Ship'])]

        target_file_path = self.folder_results + 'animation'

        for e in df_status.decision_epoch.unique():
            for a in df_status.area.unique():
                for d in df_status.deck.unique():
                    for s in ['empty', 'empty_x', 'reserved', 'taken', 'taken_x', 'pathway', 'barrier']:

                        dummy_row = {'decision_epoch': e,
                                    'real_time': 0,
                                    'position': 0,
                                    'area': a,
                                    'deck': d,
                                    'row': -99,
                                    'lane': -99,
                                    'status': s,
                                    'possible_decision': '',
                                    'score': 0,
                                    'text': '',
                                    'history': ''
                                    }
                        # df_status = df_status.append(dummy_row, ignore_index=True)

                        df_status = pd.concat([df_status, pd.DataFrame([dummy_row])], ignore_index=True)

        df_status['status'] = df_status.apply(
            lambda row: f"{row['status']}_x" if row['possible_decision'] == 'X' else row['status'],
            axis=1)

        map_status_color = dict(empty='lawngreen', empty_x='blue',
                                taken='darkred', taken_x='blue',
                                reserved='gold',
                                pathway='white', barrier='grey')

        map_status_symbol = dict(empty='circle', empty_x='circle',
                                taken='square', taken_x='square',
                                reserved='hexagon', pathway='square', barrier='square')

        fig = px.scatter(df_status, x='lane', y='row', color='status',
                        animation_frame='decision_epoch',
                        text='text',
                        facet_col='deck',
                        labels=dict(row='Rows', lane='Lanes', deck='Deck',
                                    status='Category',
                                    decision_epoch='Decision Epoch',
                                    empty_x='empty (possible decision)',
                                    taken_x='taken (possible decision)'),
                        symbol='status',
                        symbol_map=map_status_symbol,
                        color_discrete_map=map_status_color,
                        title=title,
                        category_orders=dict(
                            status=['barrier', 'pathway', 'empty', 'empty_x', 'reserved', 'taken', 'taken_x']
                        ),
                        hover_data=dict(
                            row=False, lane=False, status=False, history=True
                        ),
                        range_x=[0.5, df_status['lane'].max() + 0.5],
                        range_y=[df_status['row'].max() + 0.8, 0.2],
                        width=len(df_status['lane'].unique()) * 120,
                        height=len(df_status['row'].unique()) * 60
                        )

        fig.update_traces(
            marker={'size': 20},
            textposition='middle center',
            textfont=dict(
                size=12,
                color="white"
            )
        )

        fig.update_layout(
            # yaxis=dict(type='category'),
            yaxis=dict(
                tickmode='linear',
                tick0=1,
                dtick=1,
            ),
            xaxis=dict(
                tickmode='linear',
                tick0=1,
                dtick=1,
            )
        )

        # update duration of frames and transition (only works if there are multiple frames)
        if len(fig.frames) > 1:
            fig.layout.updatemenus[0].buttons[0].args[1]['frame']['duration'] = 500
            fig.layout.updatemenus[0].buttons[0].args[1]['transition']['duration'] = 0

            # title for frame (within the animation)
            for button in fig.layout.updatemenus[0].buttons:
                button['args'][1]['frame']['redraw'] = True

            for e in range(len(fig.frames)):
                fig.frames[e]['layout'].update(title_text='Epoch ' + str(e))
                
        fig.write_html(target_file_path + '.html', auto_play=False)        

        print('completed')

    # Function: Stat
    def stat(self):

        return 'Realization ' + str(self.composition.name) \
               + ': # Cargo: ' + str(len(self.Cargo)) + ' (thereof ' + str(len(self.late_cargo)) + ' late cargo)' \
               + ', # Tugs: ' + str(len(self.Tugs))

    # Function: Active decisions per deck
    def active_decisions_per_deck(self):
        open_decision_per_deck = {i: 0 for i in self.Ship.decks}

        for d in self.list_of_decisions:
            if not d.is_completed:
                if d.busy_on_ship_deck is not None:
                    open_decision_per_deck[d.busy_on_ship_deck] += 1

        return open_decision_per_deck

    # Function: Transition
    def transition(self, decision, print_steps, print_high_level_steps, all_possible_decisions):

        if decision is None:
            t_next_event = min([time for time in self.events_at_time.keys() if time > self.t],
                               default=None)

            t_next_late_cargo = None if len(self.late_cargo) == 0 else self.late_cargo[
                0].arrival_time_in_sec

            if t_next_late_cargo is not None and t_next_late_cargo <= t_next_event:
                # late cargo
                self.arrival_of_late_cargo(c=self.late_cargo[0])

                if t_next_event is not None and t_next_late_cargo == t_next_event:
                    # next event
                    self.next_event(events_at_t=t_next_event)

            else:
                if t_next_event is not None:
                    # next event
                    self.next_event(events_at_t=t_next_event)

            if not self.unloading_completed:
                if all(self.status[c] == 'completed' for c in self.Ship.initial_cargo):
                    # unloading completed
                    self.unloading_completed = True
                    self.unloading_completion_time = self.real_time

                    # print status
                    if print_steps or print_high_level_steps:
                        print('-- Unloading completed in epoch ' + str(self.e) + ' (' + get_time(
                            self.real_time) + '): ' + self.stat_current_state)

            if not self.ramp_to_lower_deck_had_been_opened:
                if all(self.status[epos] == 'empty' for epos in self.instance.ramp_positions_to_lower_deck):
                    self.ramp_to_lower_deck_had_been_opened = True

            if t_next_event is None and t_next_late_cargo is None:
                # completed policy
                self.policy_completed = True

                # print status
                if print_steps or print_high_level_steps:
                    print('-- Loading completed in epoch ' + str(self.e) + ' (' + get_time(
                        self.real_time) + '): ' + self.stat_current_state)

        else:
            # update status
            self.store_status(all_possible_decisions=all_possible_decisions)

            # update model
            decision.update_model(model=self)

            # save decision
            self.list_of_decisions.append(decision)

    # Function: Get all possible decision
    def get_all_possible_decision(self):
        # unloading
        all_possible_decisions = self.all_unloading_decisions()

        # loading
        all_possible_decisions += self.all_loading_decisions()

        # skip decisions
        all_possible_decisions = self.skip_decisions(all_possible_decisions=all_possible_decisions)

        return all_possible_decisions

    # Function: Find decision
    def find_decision(self):

        all_possible_decisions = self.get_all_possible_decision()

        if len(all_possible_decisions) == 0 \
                or (len(all_possible_decisions) == 1 and all_possible_decisions[0] is None):
            return None, all_possible_decisions

        if self.composition.policy == 'Random':
            remaining_decisions = all_possible_decisions
            decision = self.composition.rng.choice(all_possible_decisions)

        else:
            if self.composition.decision_policy == 'Feature Counting':
                remaining_decisions = self.tree.filter_with_feature_weights(possible_decisions=all_possible_decisions)

            elif self.composition.decision_policy == 'Feature Hierarchy':
                remaining_decisions = self.tree.filter_with_hierarchy(possible_decisions=all_possible_decisions)

            else:
                remaining_decisions = all_possible_decisions

            decision = get_decision_with_deck_lane_row_rule(remaining_decisions=remaining_decisions)

        decision.total_decisions = len(all_possible_decisions)
        decision.pct_filtered_decisions = round(
            (len(all_possible_decisions) - len(remaining_decisions)) / len(all_possible_decisions), 2)

        # print(decision)

        return decision, all_possible_decisions

    # Function: Skip decisions new
    def skip_decisions_new(self, all_possible_decisions):
        t_next_event = min([time for time in self.events_at_time.keys() if time > self.t],
                           default=None)

        if t_next_event is None:
            return all_possible_decisions
        else:
            # print(self.active_decisions_per_deck())

            unloading_cargo_on_path_to_lower_deck = False
            ship_positions_deck_0 = []
            ship_positions_deck_1 = []
            ship_positions_deck_2 = []
            DH_ship_positions = []
            TH_ship_positions = []

            for d in all_possible_decisions:
                if not d.is_loading and d.on_path_to_deck_0:
                    unloading_cargo_on_path_to_lower_deck = True

                if d.ship_position.deck.level == 0:
                    if d.ship_position not in ship_positions_deck_0:
                        ship_positions_deck_0.append(d.ship_position)
                elif d.ship_position.deck.level == 1:
                    if d.ship_position not in ship_positions_deck_1:
                        ship_positions_deck_1.append(d.ship_position)
                elif d.ship_position.deck.level == 2:
                    if d.ship_position not in ship_positions_deck_2:
                        ship_positions_deck_2.append(d.ship_position)

                if d.vehicle is None:
                    if d.ship_position not in DH_ship_positions:
                        DH_ship_positions.append(d.ship_position)
                else:
                    if d.ship_position not in TH_ship_positions:
                        TH_ship_positions.append(d.ship_position)

            path_to_lower_deck = self.ramp_to_lower_deck_had_been_opened or unloading_cargo_on_path_to_lower_deck
            p_skip = 0 if path_to_lower_deck else 0.0

            # p_skip += 0.01 * len(ship_positions_deck_0)
            # p_skip += 0.01 * len(ship_positions_deck_1) #if self.ramp_to_lower_deck_had_been_opened else 0
            # p_skip += 0.01 * len(ship_positions_deck_2)

            # p_skip += 0.01 * len(DH_ship_positions)
            # p_skip -= 0.01 * len(TH_ship_positions)

            p_skip = min(max(0, p_skip), 1)

            # p_skip = 0

            do_skip = self.composition.rng.choice([True, False], p=[p_skip, 1 - p_skip])

            if do_skip:
                # print('SKIP (p=' + str(p_skip) + ') at ' + str(self.t) + ' (e=' + str(self.e) + ')')
                # print(' Has path to lower deck: ' + str(path_to_lower_deck))
                # print(' Ship positions on deck (0, 1, 2): (' + str(len(ship_positions_deck_0)) + ',' + str(len(ship_positions_deck_1)) + ',' + str(len(ship_positions_deck_2)) + ')')
                # print(' Ship positions (DH, TH): (' + str(len(DH_ship_positions))+ ',' + str(len(TH_ship_positions)) + ')')
                self.count_skipped_decisions += 1
                return []
            else:
                return all_possible_decisions

    # Function: Skip decisions
    def skip_decisions(self, all_possible_decisions):

        if self.t_last_event_in_sec >= self.t:
            skip_tug_decision = False
            skip_driver_decision = False

            if self.composition.skip_prob_tug > 0:
                skip_tug_decision = self.composition.rng.choice([True, False], p=[self.composition.skip_prob_tug,
                                                                       1 - self.composition.skip_prob_tug])

            if self.composition.skip_prob_driver > 0:
                skip_driver_decision = self.composition.rng.choice([True, False], p=[self.composition.skip_prob_driver,
                                                                          1 - self.composition.skip_prob_driver])

            if skip_tug_decision or skip_driver_decision:
                updated_decisions = []
                self.count_skipped_decisions += 1

                for d in all_possible_decisions:
                    if skip_tug_decision:
                        # requires tug AND upper deck (deck 2) AND ramp to lower deck had not be opened
                        if d.vehicle is not None and d.ship_position.deck.level == 2 and not self.ramp_to_lower_deck_had_been_opened:
                            print('decision skipped: ' + str(d))
                            pass
                        else:
                            updated_decisions.append(d)

                    if skip_driver_decision:
                        # self-driving vehicle AND any at least one tug is waiting
                        if d.vehicle is None and any(self.status[tug] == 'available' for tug in self.Tugs):
                            # print('decision skipped: ' + str(d))
                            pass
                        else:
                            updated_decisions.append(d)

                # print('before: ' + str(len(all_possible_decisions)) + ' vs. after: ' + str(len(updated_decisions)))
                return updated_decisions

        return all_possible_decisions

    # Function: Store status
    def store_status(self, all_possible_decisions=None):
        do_function = True
        for p in self.Ship.positions:
            if self.status[p] in ['taken', 'taken (c)']:
                if self.cargo_of_pos[p] is None:
                    print('Error: Position has status -taken- but there is no cargo Position: ' + str(p) +
                          ', status: ' + str(self.status[p]))
                    do_function = False

        if do_function:
            decision_pos = {}
            if all_possible_decisions is not None:
                for d in all_possible_decisions:
                    if d is not None:
                        if d.is_loading:
                            decision_pos[d.target] = d
                        else:
                            # unloading
                            decision_pos[self.pos_of_cargo[d.cargo]] = d

            else:
                decision_pos = {}

            # 'decision_epoch', 'real_time', 'pos', 'area', 'deck', 'row', 'lane', 'status',
            # 'possible_decision', 'text', 'history'

            if self.composition.plot_animation:
                self.stored_status.extend([
                    [self.e,
                     get_time(self.real_time),
                     str(p),
                     p.area,
                     p.deck.level,
                     p.row,
                     p.lane,
                     # status
                     'taken' if self.status[p] == 'taken (c)' else self.status[p],
                     # possible decision
                     'X' if p in decision_pos else '',
                     # text
                     self.text_for_position(pos=p),
                     # history
                     self.history[p]]
                    for p in self.Ship.positions  # + self.Terminal.positions
                ])

    # Function: Get unloading cargo
    def get_unloading_cargo(self):

        active_decisions_per_deck = self.active_decisions_per_deck()

        unloading_cargo = []
        for deck, decision_per_deck in active_decisions_per_deck.items():
            if decision_per_deck < self.composition.max_decisions_per_deck:
                for pos in deck.positions:
                    if self.status[pos] == 'taken':
                        if pos.deck.level == 0:
                            if any(self.status[epos] != 'empty'
                                   for epos in self.instance.ramp_positions_to_lower_deck):
                                # elevator is blocked
                                continue
                        elif pos.deck.level == 1 and pos.row == pos.area.n_rows:
                            # direct access to ramp
                            unloading_cargo.append(self.cargo_of_pos[pos])
                            continue

                        combinations = []

                        if pos.deck.level == 0:
                            if pos.row <= 2:
                                combinations = [
                                    [pos.neighbors['bl'],
                                     pos.neighbors['bb'],
                                     pos.neighbors['br']]
                                ]
                            else:
                                combinations = [
                                    [pos.neighbors['tr'],
                                     pos.neighbors['tl'],
                                     pos.neighbors['tt']]
                                ]

                        elif pos.deck.level == 1:
                            combinations = [
                                [pos.neighbors['bl'],
                                 pos.neighbors['bb'],
                                 pos.neighbors['br']]
                            ]
                        elif pos.deck.level == 2:
                            combinations = [
                                [pos.neighbors['tr'],
                                 pos.neighbors['tl'],
                                 pos.neighbors['tt']]
                            ]

                        for combination in combinations:
                            if all(c_pos is None
                                   or c_pos.is_barrier
                                   or c_pos.is_pathway
                                   or self.status[c_pos] == 'empty'
                                   for c_pos in combination):
                                unloading_cargo.append(self.cargo_of_pos[pos])
                                break

        return unloading_cargo

    # Function: Get loading cargo from terminal
    def get_loading_cargo_from_terminal(self):

        loading_cargo_in_terminal = []

        # find loading cargo
        for pos in self.Terminal.positions:
            if self.cargo_of_pos[pos] is not None and self.status[self.cargo_of_pos[pos]] == 'available':
                if self.cargo_of_pos[pos].is_selfdriving:
                    if pos.row == 1 or self.status[pos.neighbors['tt']] == 'empty':
                        loading_cargo_in_terminal.append(self.cargo_of_pos[pos])
                else:
                    loading_cargo_in_terminal.append(self.cargo_of_pos[pos])

        return loading_cargo_in_terminal

    # Function: Get empty positions terminal
    def get_empty_positions_terminal(self, cargo):

        return [p for p in self.Terminal.positions
                if self.status[p] == 'empty' and (
                        (cargo.is_selfdriving and p.is_for_selfdriving_cargo) or
                        (not cargo.is_selfdriving and p.is_for_towed_cargo)
                )]

    # Function: Get empty positions ship
    def get_empty_positions_ship(self):

        active_decisions_per_deck = self.active_decisions_per_deck()

        empty_positions = []
        for deck, decision_per_deck in active_decisions_per_deck.items():
            if decision_per_deck < self.composition.max_decisions_per_deck:
                include_deck = False

                if deck.level == 0:
                    if all(self.status[epos] == 'empty' for epos in self.instance.ramp_positions_to_lower_deck):
                        include_deck = True
                else:
                    include_deck = True

                if include_deck:
                    for pos in deck.positions:
                        if self.status[pos] == 'empty':
                            if deck.level == 0:
                                if pos.row <= 2:
                                    combinations = [
                                        [pos.neighbors['tr'],
                                         pos.neighbors['tl'],
                                         pos.neighbors['tt']]
                                    ]
                                else:
                                    combinations = [
                                        [pos.neighbors['bl'],
                                         pos.neighbors['bb'],
                                         pos.neighbors['br']]
                                    ]

                            elif deck.level == 1:

                                if pos in self.instance.ramp_positions_to_lower_deck:
                                    if any(self.status[epos] in ['empty', 'reserved'] for epos in self.Ship.positions if
                                           epos.deck.level == 0):
                                        # pos is required to first fill the lower deck -> go to next postion via continue
                                        continue

                                combinations = [
                                    [pos.neighbors['tr'],
                                     pos.neighbors['tl'],
                                     pos.neighbors['tt']]
                                ]

                            else:
                                # deck.level == 2:
                                combinations = [
                                    [pos.neighbors['bl'],
                                     pos.neighbors['bb'],
                                     pos.neighbors['br']]
                                ]

                            if pos_qualifies_for_loading(model=self, combinations=combinations):
                                empty_positions.append(pos)

        return empty_positions

    # Function: Arrival of late cargo
    def arrival_of_late_cargo(self, c):
        self.status[c] = 'available'
        # print(str(c.arrival_time_in_sec) + ': ', end='')
        # print('current pos: ' + str(self.pos_of_cargo[c]))
        self.pos_of_cargo[c] = self.areas['Port'].entry
        # print('new pos: ' + str(self.pos_of_cargo[c]))

        d = Decision(epoch=self.e, time_start_in_sec=c.arrival_time_in_sec,
                     vehicle=None, cargo=c, target=c.initial_position,
                     is_loading=True, model=self)
        d.update_model(model=self)

        self.late_cargo = self.late_cargo[1:]
        self.t = c.arrival_time_in_sec

    # Function: Next event
    def next_event(self, events_at_t):

        # consider impact of next events (there might be multiple events at time t)
        for ne in self.events_at_time[events_at_t]:
            ne.consider_impact(model=self)

        self.t = events_at_t

    # Function: All unloading decisions
    def all_unloading_decisions(self):
        unloading_decisions = []

        cargo_to_be_unloaded = self.get_unloading_cargo()

        for cargo in cargo_to_be_unloaded:
            if cargo.is_selfdriving:
                # self-driving cargo
                targets = [self.areas['Port'].exit]
                tugs = [None]
            else:
                # towed cargo
                targets = self.get_empty_positions_terminal( cargo=cargo)
                tugs = [tug for tug in self.Tugs if self.status[tug] == 'available']

            for tug in tugs:
                for target in targets:
                    unloading_decisions.append(
                        Decision(epoch=self.e, time_start_in_sec=self.t,
                                 vehicle=tug, cargo=cargo, target=target, is_loading=False, model=self)
                    )

        return unloading_decisions

    # Function: All loading decisions
    def all_loading_decisions(self):
        loading_decisions = []

        cargo_to_be_loaded = self.get_loading_cargo_from_terminal()

        targets = self.get_empty_positions_ship()
        tugs = [tug for tug in self.Tugs if self.status[tug] == 'available']

        for cargo in cargo_to_be_loaded:

            tug_list = [None] if cargo.is_selfdriving else tugs

            for tug in tug_list:
                for target in targets:
                    if (cargo.is_selfdriving and target.is_for_selfdriving_cargo) or (
                            not cargo.is_selfdriving and target.is_for_towed_cargo):

                        loading_decisions.append(
                            Decision(epoch=self.e, time_start_in_sec=self.t, vehicle=tug, cargo=cargo, target=target,
                                     is_loading=True, model=self)
                        )

        return loading_decisions

    # Function: Text for position
    def text_for_position(self, pos):
        text = ''

        if pos.is_elevator:
            text += '*'
        else:
            if self.status[pos] in ['taken', 'taken (c)'] and self.cargo_of_pos[pos].is_selfdriving:
                text += 'S'
            elif self.status[pos] in ['taken', 'taken (c)'] and not self.cargo_of_pos[pos].is_selfdriving:
                text += 'T'

        if pos in self.double_cycling_ship_positions:
            text += '.'

        return text

    # Function: Df decisions
    def df_decisions(self):
        df_columns = ['decision', 'decision_epoch', 'time_start_in_sec',
                      'tug', 'cargo', 'target']

        df_as_lists = []
        for d in self.list_of_decisions:
            df_as_lists.append([
                str(d), d.epoch, d.time_start_in_sec,
                str(d.vehicle), str(d.cargo), d.target.name
            ])

        df_decisions = pd.DataFrame(df_as_lists, columns=df_columns)

        return df_decisions.sort_values(['decision_epoch'], ascending=True)

    # Function: Df events
    def df_events(self):
        df_columns = ['decision_epoch', 'decision',
                      'event', 'start', 'time_start_in_sec', 'duration_in_sec', 'time_end_in_sec', 'end',
                      'tug', 'cargo', 'type',
                      'source', 'source_area', 'source_row', 'source_lane',
                      'target', 'target_area', 'target_row', 'target_lane']

        df_as_lists = []
        for event_time_in_sec, events in self.events_at_time.items():
            for e in events:
                for pe in e.postponed_events:
                    df_as_lists.append([
                        pe.decision.epoch,
                        str(pe.decision),
                        str(pe),
                        sec_to_real_time(pe.time_start_in_sec),
                        pe.time_start_in_sec, pe.task.duration_in_sec, pe.time_end_in_sec,
                        sec_to_real_time(pe.time_end_in_sec),
                        str(pe.task.vehicle), pe.task.cargo, pe.task.type,
                        pe.task.source.name, pe.task.source.area.name, str(pe.task.source.row),
                        str(pe.task.source.lane),
                        pe.task.target.name, pe.task.target.area.name, str(pe.task.target.row), str(pe.task.target.lane)
                    ])

                df_as_lists.append([
                    e.decision.epoch,
                    str(e.decision),
                    str(e), sec_to_real_time(e.time_start_in_sec),
                    e.time_start_in_sec, e.task.duration_in_sec, e.time_end_in_sec, sec_to_real_time(e.time_end_in_sec),
                    str(e.task.vehicle), e.task.cargo, e.task.type,
                    e.task.source.name, e.task.source.area.name, str(e.task.source.row), str(e.task.source.lane),
                    e.task.target.name, e.task.target.area.name, str(e.task.target.row), str(e.task.target.lane)
                ])

        df_events = pd.DataFrame(df_as_lists, columns=df_columns)

        return df_events.sort_values(['decision_epoch', 'time_start_in_sec'], ascending=True)

    # Function: Df status
    def df_status(self):
        df_columns = [
            'decision_epoch', 'real_time', 'position', 'area', 'deck', 'row', 'lane', 'status',
            'possible_decision', 'text', 'history'
        ]

        new_df = pd.DataFrame(self.stored_status, columns=df_columns)

        # new_df = new_df.sort_values(['decision_epoch', 'area', 'deck', 'row', 'lane'],
        #                             ascending=[True, False, False, False, False])

        return new_df

    @property
    # Function: Real time
    def real_time(self):
        return current_time + datetime.timedelta(days=0, seconds=self.t)

    @property
    # Function: Stat current state
    def stat_current_state(self):
        # Unloading
        available_uCargo = get_cargo(cargo=self.Cargo, area=self.Ship, model=self,
                                     target_status='available', is_selfdriving=False)

        available_aCargo = get_cargo(cargo=self.Cargo, area=self.Ship, model=self,
                                     target_status='available', is_selfdriving=True)

        empty_positions = get_positions(area=self.Terminal, status=self.status, target_status='empty',
                                        valid_for_uCargo=True)
        return_str = 'Unloading (aCargo/uCargo): (' + str(len(available_aCargo)) + '/' + str(
            len(available_uCargo)) + ') available, ' \
                     + str(len(empty_positions)) + ' empty positions in Terminal'

        # Loading
        available_uCargo = get_cargo(cargo=self.Cargo, area=self.Terminal, model=self,
                                     target_status='available', is_selfdriving=False)

        available_aCargo = get_cargo(cargo=self.Cargo, area=self.Terminal, model=self,
                                     target_status='available', is_selfdriving=True)

        empty_positions = get_positions(area=self.Ship, status=self.status, target_status='empty',
                                        valid_for_uCargo=True)
        return_str += ' <-> Loading (aCargo/uCargo): (' + str(len(available_aCargo)) + '/' + str(
            len(available_uCargo)) + ') available, ' \
                      + str(len(empty_positions)) + ' empty positions in Ship'

        return return_str

    @property
    # Function: Folder results
    def folder_results(self):
        target_folder = 'results/detailed/' + str(self.composition.name) + ' R' + str(self.id) + '/'
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)

        return target_folder