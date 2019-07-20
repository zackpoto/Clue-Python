#!/usr/bin/env python
import itertools

from playerproxy import Player, main
from cards import CARDS
from protocol import BufMessager

# import crash_on_ipy

class Card:
    def __init__(self, name, type):
        self.name = name                    # name of this card - String (ex. "Mu", "Re", and "Ba")
        self.possible_owners = []           # all of the players who have not disproved this card - List[Players]
        self.owner = None                   # owner of this card - Player
        self.in_solution = False            # if this card is in the solution - Boolean
        self.disproved_to = set()           # players who have disproved the card - {Player}
        self.type = type                    # type of the card - CardType (type1/suspect, type2/weapon, etc...)

    def __repr__(self):
        return self.name

    def log(self, *args, **kwargs):
        pass

    def set_owner(self, owner):
        assert self.owner is None           # Check if this card already has an owner
        assert self in owner.may_have       # Check if this card has not already been disproved by the owner-input
        for player in self.possible_owners: # Remove this card from the "may_have" set of every player who has not
            player.may_have.remove(self)    # disproved this card
        self.possible_owners.clear()        # Empty this card's "possible_owners" list
        self.owner = owner                  # Set the owner of this card to the owner-input
        owner.must_have.add(self)           # Add this card to the "must_have" set of the owner-input
        self.type.rest_count -= 1           # Lower the "rest_count" of this card's CardType by 1 to indicate that
                                            # there is one less card of this type without a known owner.

    def set_as_solution(self):
        # import pdb; pdb.set_trace()
        assert self.owner is None           # Check if this card has an owner
        self.type.solution = self           # Set this card as the solution of this card's CardType
        self.in_solution = True             # Set this card's "in_solution" variable to True
        for player in self.possible_owners: # Remove this card from the "may_have" set of every player who has not
            player.may_have.remove(self)    # disproved this card
        self.possible_owners.clear()        # Empty this card's "possible_owners" list
        self.type.rest_count -= 1           # Lower the "rest_count" of this card's CardType by 1

    def __hash__(self):
        return hash(self.name)


class CardType:
    def __init__(self, type_id):
        self.type_id = type_id                                          # number of this CardType - Int (1 -> suspect, 2 -> weapon, etc...)
        self.cards = [Card(name, self) for name in CARDS[type_id]]      # list of the cards of this CardType - List
        self.rest_count = len(self.cards)                               # number of cards in this CardType without a known owner - Int
        self.solution = None                                            # the card of this CardType in the solution - Player


class PlayerInfo:
    def __init__(self, id):
        self.id = id                        # the position of this Player in terms of the order of the card dealing - Int
        self.must_have = set()              # set of cards this player must have / has disproved - Set
        self.may_have = set()               # set of cards this any player has not disproved - Set
        self.selection_groups = []          # list of sets of cards, in which at least this player MUST have one - List(Set(Card))
        self.n_cards = None                 # number of cards this player has in their hand - Int

    def __hash__(self):
        return hash(self.id)

    def set_have_not_card(self, card):
        if card in self.may_have:
            self.may_have.remove(card)          # remove the card-input from this Player's "may_have" set
            card.possible_owners.remove(self)   # and remove this Player from the card-input's "possible_owners" list

    def log(self, *args, **kwargs):
        pass

    def update(self):
        static = False
        updated = False
        while not static:
            static = True
            if len(self.must_have) == self.n_cards:             # If every card in Player's hand is known
                if not self.may_have:                           # If the Player has no cards in "may_have" set
                    break
                for card in self.may_have:                      # Remove this Player from the "possible_owners" list of every every card Player owns
                    card.possible_owners.remove(self)
                self.may_have.clear()                           # Empty the "may_have" set of this player
                static = False
                updated = True

            if len(self.must_have) + len(self.may_have) == self.n_cards:
                # If this number of unknown cards in the Player's hand is equal to the number of cards that this player could possibly have (not in solution or already disproved), this Player must own all of these unknown cards
                static = False
                updated = True
                for card in list(self.may_have):                # Set the owner of all of these "may_have" cards to this Player
                    card.set_owner(self)

            #filter through the sets in the selection_groups
            new_groups = []
            for group in self.selection_groups:
                group1 = []
                for card in group:
                    if card in self.must_have:                  # Discard the sets that contain a card this Player already owns
                        break
                    if card in self.may_have:                   # Keep the cards in every set that have been denied or disproved
                        group1.append(card)                     # by another player already owns
                else:
                    if len(group1) == 1:                        # If only 1 card remains in a set this Player must have this card
                        group1[0].set_owner(self)
                        updated = True
                        static = False
                    elif group1:                                # Otherwise keep the sets in the "selection_groups" list
                        new_groups.append(group1)
            self.selection_groups = new_groups

            if len(self.must_have) + 1 == self.n_cards:
                # There is only one card remaining to for the Player to disprove, so this card must be in every selection group
                cards = self.may_have.copy()
                for group in self.selection_groups:         # Find the intersection between Player's "may_have" set and
                    if self.must_have.isdisjoint(group):    # every "selection_groups" set that does
                        cards.intersection_update(group)    # not contain a card in "must_have" set

                for card in self.may_have - cards:          # Remove every other card in the Player's "may_have" set
                    static = False
                    updated = True
                    self.set_have_not_card(card)

        # assert self.must_have.isdisjoint(self.may_have)
        # assert len(self.must_have | self.may_have) >= self.n_cards
        return updated


class Suggestion:
    def __init__(self, player, cards, dplayer, dcard):
        self.player = player                        # player who made the suggestion - Player
        self.cards = cards                          # cards the player-input suggested - {Cards} or [Cards] ??
        self.dplayer = dplayer                      # player who disproved the suggestion - Player
        self.dcard = dcard                          # card used to disprove the suggestion - Card
        self.disproved = dplayer is not None        # if there was a "dplayer" then this suggestion was disproved


class AI01(Player):
    def prepare(self):
        self.set_verbosity(0)                       #????????????????????????????

    def reset(self, player_count, player_id, card_names):
        #self - AI01_Player class
        #player_count - number of players in the game
        #player_id - placement of the AI in the order of players (1 is the first player to draw a card)
        #card_names - list of cards in AI01's hand - [String]
        self.log('reset', 'id=', player_id, card_names)
        self.fail_count = 0
        self.suggest_count = 0
        self.card_types = [CardType(i) for i in range(len(CARDS))]                  # list of all CardTypes
        self.cards = list(itertools.chain(*(ct.cards for ct in self.card_types)))   # list of all Cards
        for card in self.cards:     #????????
            card.log = self.log
        self.card_map = {card.name: card for card in self.cards}        # dictionary of every card with the cards name attribute as the keys and the corresponding card object as the item
        self.owned_cards = [self.card_map[name] for name in card_names] # use this dictionary to add every card in the "card_names" list of card strings to a list of card objects
        self.players = [PlayerInfo(i) for i in range(player_count)]     # list of players
        for player in self.players: #?????????
            player.log = self.log
        self.player = self.players[player_id]                           # assign the AI01's Player object to player attribute
        for card in self.cards:                                         # add every Player to every Card's "possible_owners" list
            card.possible_owners = list(self.players)
        n_avail_cards = len(self.cards) - len(CARDS)                    # number of cards not in the solution (always 18)
        for player in self.players:
            player.may_have = set(self.cards)                           # add every Card to every Player's "may_have" set
            player.n_cards = n_avail_cards // player_count \
                + (player.id < n_avail_cards % player_count)            # assign the number of cards in each Player's hand according to their position in dealing order
        for card in self.owned_cards:                                   # set the AI's Player object as the owner of every Card the AI owns
            card.set_owner(self.player)
        for card in self.cards:                                         # for every card the AI does not own call the "set_have_not_card" function for the AI Player object
            if card not in self.owned_cards:
                self.player.set_have_not_card(card)
        self.suggestions = []                                           # list of suggestions the (AI/every player) has made ??????
        self.avail_suggestions = set(itertools.product(*CARDS))         # set of tuples of every String permutation of suspect, weapon, room
        self.possible_solutions = {                                     # dictionary with one of the tuples in "avail_suggestions" as the key and the integer 1 as the itme
            tuple(self.get_cards_by_names(cards)): 1
            for cards in self.avail_suggestions
        }
        self.filter_solutions()                                         # ??????

    def filter_solutions(self):
        new_solutions = {}
        # assert self.possible_solutions

        join = next(iter(self.possible_solutions))  #random key(/solution triple) from "possible_solutions" dictionary

        for sol in self.possible_solutions:
            for card, type in zip(sol, self.card_types):
                if card.owner or type.solution and card is not type.solution:
                    # This candidate can not be a solution because it has a
                    # card that has owner or this type is solved.
                    break
            else:
                count = self.check_solution(sol)
                if count:
                    new_solutions[sol] = count
                    join = tuple(((x is y) and x) for x, y in zip(join, sol))   # 3-item tuple (each item corresponding to a CardType) with either a Card or False depending on whether a card in "join" intersects between all "possible_solutions"

        self.possible_solutions = new_solutions
        updated = False
        for card in join:                                                       # if one of the items in the "join" tuple is not False (e.i. is a Card object) and is not already a solution, that item must be a Card in the solution
            if card and not card.in_solution:
                card.set_as_solution()
                updated = True
                self.log('found new target', card, 'in', join)

        # self.dump()
        return updated

    def check_solution(self, solution):
        """
        This must be called after each player is updated.
        """
        players = self.players
        avail_cards = set(card for card in self.cards if card.possible_owners)  # set of cards that have no known owners and are not known to be in the solution (e.i could be in the solution)
        avail_cards -= set(solution)                                            # set of available cards assuming no one owns the solution-input cards (e.i. the solution is correct)
        if len(avail_cards) >= 10:                                              # return 1 because solution is still possible (idk why 10 is significant)
            return 1
        count = 0

        def resolve_player(i, avail_cards):
            nonlocal count
            if i == len(players):                                               # if all players have been resolved the solution-input could be correct
                count += 1
                return
            player = players[i]                                                 # a Player object corresponding to the i-input integer
            n_take = player.n_cards - len(player.must_have)                     # number of cards "player" has which are unknown
            cards = avail_cards & player.may_have                               # the cards available to "player" assuming the solution-input is correct (avaible cards for all players - cards rejected by "player")
            for choice in map(set, itertools.combinations(cards, n_take)):      # iterates over the permutations of "n_take" number of cards from "cards" (i.e all the permutations of unknown cards the "player" might have)
                player_cards = player.must_have | choice                        # get the union of every permutation and the known cards of "player"
                for group in player.selection_groups:
                    if player_cards.isdisjoint(group):                          # if a selection group does not contain one of the cards in these permutation-intersections then the solution-input is incorrent because "player" would have to own one of the cards in the solution-input
                        # Invalid choice
                        break
                else:
                    resolve_player(i + 1, avail_cards - choice)                 # "resolve" the next player

        resolve_player(0, avail_cards)                                          # start resolving players
        return count

    def suggest1(self):
        choices = []
        for type in self.card_types:
            choices.append([])
            if type.solution:                                                   # if the CardType has a solution the list is extended to the cards in the player's hand that are of the CardType
                choices[-1].extend(self.player.must_have & set(type.cards))
            else:                                                               # otherwise the list is extended to the unknown cards of CardType ordered by the number of "possible_owners" each card has (order low to high)
                choices[-1].extend(sorted(
                    (card for card in type.cards if card.owner is None),
                    key=lambda card: len(card.possible_owners)))

        for sgi in sorted(itertools.product(*map(lambda x:range(len(x)), choices)),
                key=sum):
            sg = tuple(choices[i][j].name for i, j in enumerate(sgi))
            if sg in self.avail_suggestions:
                self.avail_suggestions.remove(sg)
                break
        else:
            sg = self.avail_suggestions.pop()
            self.fail_count += 1
            self.log('fail')
        self.suggest_count += 1
        return sg

    def suggest(self):
        #suggests the card from each card type with the least amount of possible owners, but no known owner
        sg = []
        for type in self.card_types:
            card = min((card for card in type.cards if card.owner is None),
                key=lambda card: len(card.possible_owners))
            sg.append(card.name)
        sg = tuple(sg)

        if sg not in self.avail_suggestions:
            sg = self.avail_suggestions.pop()
        else:
            self.avail_suggestions.remove(sg)
        return sg

    def suggestion(self, player_id, cards, disprove_player_id=None, card=None): '''handle suggestions'''
        #only instance of Suggestion
        sg = Suggestion(
            self.players[player_id],
            self.get_cards_by_names(cards),
            self.players[disprove_player_id] if disprove_player_id is not None else None,
            self.card_map[card] if card else None,
        )
        self.suggestions.append(sg)
        # Iter through the non-disproving players and update their may_have
        end_id = sg.dplayer.id if sg.disproved else sg.player.id                # end_id is the id of the disaproving player or the id of the suggestion player if the suggestion was not disproved
        for player in self.iter_players(sg.player.id + 1, end_id):              # iterate through the players between the suggestion player and the disaproving player
            if player is self.player:
                continue
            for card in sg.cards:                                               # add the suggestion cards to the cards each player cannot have if the player is not the AI
                player.set_have_not_card(card)
        if sg.disproved:
            if sg.dcard:                                                        # if the suggestion was disproved with a card the disproving player has "sg.dcard"
                if sg.dcard.owner is None:
                    sg.dcard.set_owner(sg.dplayer)
            else:                                                               # otherwise add a selection group of (sg.cards) to the disproving player
                sg.dplayer.selection_groups.append(sg.cards)
            self.possible_solutions.pop(tuple(sg.cards), None)                  # remove the (sg.cards) triple from the "possible_solutions" dictionary

        self.update()

    def update(self):
        static = False
        while not static:
            static = True
            for card in self.cards:                                             # iterate through every card
                if card.owner is not None or card.in_solution:                  # if card has known owner or is in solution skip to next card
                    continue
                if len(card.possible_owners) == 0 and card.type.solution is None:   # if the card has no possible owners it must be the solution
                    card.set_as_solution()
                    static = False

            for type in self.card_types:                                        # iterate through every cardtype
                if type.solution is not None:                                   # if the cardType has a solution skip to next cardtype
                    continue
                if type.rest_count == 1:                                        # if there is only 1 unknown card of cardtype is must be the solution
                    card = next(card for card in type.cards if card.owner is None)
                    card.set_as_solution()
                    static = False

            for player in self.players:                                         # iterate through every player
                if player is self.player:                                       # skip if the player is the AI
                    continue
                if player.update():                                             # update the player
                    static = False

            if self.filter_solutions():                                         # filter the solutions
                static = False

    def iter_players(self, start_id, end_id):
        # start_id - id of the player after the suggestion player
        # end_id - id of the of the disaproving player / or suggestion player if no one disaproved
        n = len(self.players)                                                   # number of players in the game
        for i in range(start_id, start_id + n):                                 # iterate the id of the player after the suggestion player through the suggestion player
            if i % n == end_id:                                                 # stop when it gets to the id of the disaproving player
                break
            yield self.players[i % n]                                           # return the players between the suggestion player and the disaproving player

    def accuse(self):
        if all(type.solution for type in self.card_types):                      # if every CardType has a solution return a list of all of the solution CardTypes
            return [type.solution.name for type in self.card_types]
        possible_solutions = self.possible_solutions
        if len(possible_solutions) == 1:                                        # if there is only 1 possible solution make an accusation of that solution
            return next(possible_solutions.values())

        # most_possible = max(self.possible_solutions, key=self.possible_solutions.get)
        # total = sum(self.possible_solutions.values())
        # # self.log('rate:', self.possible_solutions[most_possible] / total)
        # if self.possible_solutions[most_possible] > 0.7 * total:
        #     self.log('guess', most_possible)
        #     return [card.name for card in most_possible]

        return None

    def disprove(self, suggest_player_id, cards): '''handle the role to disprove'''
        # suggest_player_id - id number of the Player who made the suggestion
        # cards - list of cards in the suggestion - [Card]
        # return - "name" attribute the card the AI will use to disprove the suggestion - String
        cards = self.get_cards_by_names(cards)                          # cards in the suggestion - [Cards]
        sg_player = self.players[suggest_player_id]                     # player who made the suggestion - Player
        cards = [card for card in cards if card in self.owned_cards]    # cards in the suggestion that the AI owns
        for card in cards:                                              # if the AI has already disproved one of the cards to the player who made the suggestion, reveal that card again
            if sg_player in card.disproved_to:
                return card.name
        return max(cards, key=lambda c: len(c.disproved_to)).name       # otherwise show the card that has been shown to the greatest number of opponents

    def accusation(self, player_id, cards, is_win):
        # player_id - id number of the Player who made the accusation
        # cards - list of cards in the accusation - [Card]
        # is_win - was the accusation accurate - Boolean
        if not is_win:                                                  # if the accusation was incorrect
            cards = tuple(self.get_cards_by_names(cards))
            self.possible_solutions.pop(cards, None)                    # remove the solution from "possible_solutions" dictionary

# NOTE: uncomment the code below so that the cards in the accusation are removed from the may_have list of the accuser
# follows the reasonable but not 100% accurate assumption that a player would never make an accusation with cards they have in their hand

            # player = self.players[player_id]
            # for card in cards:
            #     player.set_have_not_card(card)
            # player.update()

        else:                                                           # we lost :(  :(
            self.log('fail rate:', self.fail_count / (1e-8 + self.suggest_count))
            self.log('fail count:', self.fail_count, 'suggest count:', self.suggest_count)

    def get_cards_by_names(self, names):
        # names - iterable container with the names of some collection of cards - {String} or [String]
        return [self.card_map[name] for name in names]                  # return a list of the Card's correspinding to the names-input - [Card]

    def dump(self):                                                     # a lot of logging
        self.log()
        for player in self.players:
            self.log('player:', player.id, player.n_cards,
                sorted(player.must_have, key=lambda x: x.name),
                sorted(player.may_have, key=lambda x: x.name),
                '\n    ',
                player.selection_groups)
        self.log('current:', [type.solution for type in self.card_types])
        self.log('possible_solutions:', len(self.possible_solutions))
        for sol, count in self.possible_solutions.items():
            self.log('  ', sol, count)
        self.log('id|', end='')

        def end():
            return ' | ' if card.name in [g[-1] for g in CARDS] else '|'

        for card in self.cards:
            self.log(card.name, end=end())
        self.log()
        for player in self.players:
            self.log(' *'[player.id == self.player.id] + str(player.id), end='|')
            for card in self.cards:
                self.log(
                    ' ' + 'xo'[player in card.possible_owners or player is card.owner],
                    end=end())
            self.log()

if __name__ == '__main__':
    main(AI01, BufMessager)
