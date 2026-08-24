import os
from flask import Blueprint, jsonify, request
from minions import get_all_minions
from zone_teams import ZONE_TEAMS
from game_engine.events.event_templates import EVENT_SCREEN_REGISTRY, EVENT_VISIT_RULES
from game_engine.events.events import (
    STORY_EVENTS, BASIC_EVENTS, ALL_CUSTOM_EVENTS,
    CROSSROADS_EVENTS, FEY_ZONE_EVENTS, CONSTRUCT_ZONE_EVENTS,
    CULT_ZONE_EVENTS, UNDEAD_ZONE_EVENTS, GREAT_HUNT_EVENTS,
    # Sub-events (accessed via chains, not standalone)
    BELL_TOWER_SUB_EVENTS, GREAT_HUNT_SUB_EVENTS, CROSSROADS_SUB_EVENTS,
    FEY_ZONE_SUB_EVENTS, CONSTRUCT_ZONE_SUB_EVENTS, CULT_ZONE_SUB_EVENTS,
    UNDEAD_ZONE_SUB_EVENTS
)
from config import EVENT_SCALING

collection_api = Blueprint('collection_api', __name__)

# Directory holding the original minion artwork.
_ORIGINAL_IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'images', 'original')


def _available_minion_images():
    """Set of image filenames that actually exist on disk.

    Some minions (e.g. certain boss/summon units) reference artwork that has not
    been added yet. Those still function in combat, but we hide them from the
    Collection browser so it never shows blank cards.
    """
    try:
        return {f for f in os.listdir(_ORIGINAL_IMAGES_DIR) if f.lower().endswith('.png')}
    except OSError:
        return set()


@collection_api.route('/minions', methods=['GET'])
def get_collection_minions():
    """
    Get all minions in the game for the collection view

    Query parameters:
    - tier: Filter by tier (1-6 or 'all')
    - tribe: Filter by tribe
    - keyword: Filter by keyword
    - search: Search minion names
    - sort_by: Sort field (name, tier, health, attack)
    """
    try:
        from flask import session
        from models import Player

        # Get all minions
        all_minions = get_all_minions()

        # Only show minions whose artwork exists on disk — hides units with
        # missing images (they still work in combat) so the grid has no blanks.
        available_images = _available_minion_images()

        # Get player's equipped images if logged in
        equipped_images = {}
        player_id = session.get('player_id')
        if player_id:
            player = Player.query.get(player_id)
            if player:
                equipped_images = player.get_equipped_images()

        # Get query parameters
        tier_filter = request.args.get('tier', 'all')
        tribe_filter = request.args.get('tribe', 'all')
        keyword_filter = request.args.get('keyword', 'all')
        search_query = request.args.get('search', '').lower()
        sort_by = request.args.get('sort_by', 'tier')

        # Filter minions
        filtered_minions = []
        for minion in all_minions:
            # Skip minions whose artwork is missing so the grid never shows a
            # blank card. These units still exist and function in combat.
            image_file = minion.get('image', '')
            if not image_file or image_file not in available_images:
                continue

            # Tier filter
            if tier_filter != 'all':
                try:
                    tier_value = int(tier_filter)
                    if minion.get('tier') != tier_value:
                        continue
                except ValueError:
                    pass

            # Tribe filter (minions use 'type' field which can be string or list)
            if tribe_filter != 'all':
                minion_type = minion.get('type', '')
                # Handle type being a list or string
                if isinstance(minion_type, list):
                    if tribe_filter not in minion_type:
                        continue
                else:
                    if minion_type != tribe_filter:
                        continue

            # Keyword filter
            if keyword_filter != 'all':
                minion_keywords = minion.get('keywords', [])
                if keyword_filter not in minion_keywords:
                    continue

            # Search filter
            if search_query:
                minion_name = minion.get('name', '').lower()
                if search_query not in minion_name:
                    continue

            # Format minion type as string (handle list or string)
            minion_type = minion.get('type', '')
            if isinstance(minion_type, list):
                type_str = ', '.join(minion_type) if minion_type else ''
            else:
                type_str = minion_type

            # Format minion for collection view
            # Generate a unique ID based on name and tier for frontend use
            minion_id = f"{minion.get('name', 'unknown').lower().replace(' ', '_')}_{minion.get('tier', 1)}"

            # Determine image path based on equipped images
            image_filename = minion.get('image', '')
            if image_filename:
                image_id = image_filename.replace('.png', '')
                if image_id in equipped_images:
                    image_path = f"images/{equipped_images[image_id]}/{image_filename}"
                else:
                    image_path = f"images/original/{image_filename}"
            else:
                image_path = None

            collection_minion = {
                'id': minion_id,
                'name': minion.get('name', 'Unknown'),
                'tier': minion.get('tier', 1),
                'type': type_str,
                'health': minion.get('health', 0),
                'attack': minion.get('attack', 0),
                'keywords': minion.get('keywords', []),
                'rarity': minion.get('rarity', 'common'),
                'image': image_filename,
                'image_path': image_path
            }

            filtered_minions.append(collection_minion)

        # Sort minions
        if sort_by == 'name':
            filtered_minions.sort(key=lambda m: m['name'])
        elif sort_by == 'tier':
            filtered_minions.sort(key=lambda m: (m['tier'], m['name']))
        elif sort_by == 'health':
            filtered_minions.sort(key=lambda m: (-m['health'], m['name']))
        elif sort_by == 'attack':
            filtered_minions.sort(key=lambda m: (-m['attack'], m['name']))

        return jsonify({
            'success': True,
            'minions': filtered_minions,
            'total': len(filtered_minions)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@collection_api.route('/npc-bands', methods=['GET'])
def get_collection_npc_bands():
    """
    Get all NPC encounter bands for the collection view

    Query parameters:
    - zone: Filter by zone
    - tier: Filter by tier (1-6 or 'all')
    - search: Search band names
    """
    try:
        # Get query parameters
        zone_filter = request.args.get('zone', 'all')
        tier_filter = request.args.get('tier', 'all')
        search_query = request.args.get('search', '').lower()

        # Build minion lookup for stats
        minion_lookup = {}
        for minion in get_all_minions():
            minion_lookup[minion.get('name')] = {
                'health': minion.get('health', 0),
                'attack': minion.get('attack', 0)
            }

        # Build bands list from ZONE_TEAMS
        all_bands = []
        for tier_key, zones in ZONE_TEAMS.items():
            # Extract tier number from key (e.g., 'tier_1' -> 1)
            tier_num = int(tier_key.split('_')[1])

            # Tier filter
            if tier_filter != 'all':
                try:
                    tier_value = int(tier_filter)
                    if tier_num != tier_value:
                        continue
                except ValueError:
                    pass

            for zone_name, teams in zones.items():
                # Zone filter
                if zone_filter != 'all' and zone_filter != zone_name:
                    continue

                # Search filter
                if search_query and search_query not in zone_name.lower():
                    continue

                # Each team becomes a band entry
                for idx, team in enumerate(teams):
                    band_name = f"{zone_name.replace('_', ' ').title()} - Band {idx + 1}"

                    # Parse minions in the band
                    minions = []
                    for minion_entry in team:
                        if isinstance(minion_entry, dict):
                            # Custom minion with overrides (special stats)
                            name = minion_entry.get('name', 'Unknown')
                            minions.append({
                                'name': name,
                                'health': minion_entry.get('health'),
                                'attack': minion_entry.get('attack'),
                                'custom': True  # Flag for special stats
                            })
                        else:
                            # String minion name - look up normal stats
                            stats = minion_lookup.get(minion_entry, {'health': 0, 'attack': 0})
                            minions.append({
                                'name': minion_entry,
                                'health': stats['health'],
                                'attack': stats['attack'],
                                'custom': False
                            })

                    all_bands.append({
                        'name': band_name,
                        'zone': zone_name,
                        'tier': tier_num,
                        'minions': minions
                    })

        return jsonify({
            'success': True,
            'bands': all_bands,
            'total': len(all_bands)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def extract_options_from_event(event_data):
    """
    Extract options from an event definition by looking at its screens.
    For make_choice screens, extracts from the choices array.
    For other screen types, generates a single option from the screen parameters.
    """
    options = []
    screens = event_data.get('screens', [])

    for screen in screens:
        screen_type = screen.get('type', '')
        params = screen.get('parameters', {})

        if screen_type == 'make_choice':
            # Extract options from choices array - this is the primary source
            choices = params.get('choices', [])
            for choice in choices:
                option = {
                    'name': choice.get('name', 'Unknown'),
                    'tooltip': choice.get('tooltip', choice.get('description', '')),
                }

                # Determine cost from various fields
                if choice.get('gold_cost'):
                    cost = choice['gold_cost']
                    # Format cost string
                    if cost == 'tier * 3':
                        option['cost'] = 'tier × 3 gold'
                    elif cost == 'tier * 4':
                        option['cost'] = 'tier × 4 gold'
                    elif cost == 'tier * 6':
                        option['cost'] = 'tier × 6 gold'
                    elif isinstance(cost, str) and cost.isdigit():
                        option['cost'] = f'{cost} gold'
                    else:
                        option['cost'] = str(cost) + ' gold'
                elif choice.get('health_cost'):
                    option['cost'] = f"{choice['health_cost']} HP"
                elif choice.get('health_cost_tracker'):
                    option['cost'] = 'HP (Ad Nauseam)'
                elif choice.get('cost_type') == 'gold':
                    multiplier = choice.get('cost_multiplier', 1)
                    option['cost'] = f'tier × {multiplier} gold'
                else:
                    option['cost'] = 'Free'

                # Add condition if present
                if choice.get('condition'):
                    option['condition'] = choice['condition']

                options.append(option)

    return options


def get_basic_event_options(event_id, event_data):
    """
    Get options for basic events that don't use make_choice screens.
    These events have specialized screen types (select_minion, select_buff_type, combat, shop, statue).
    """
    screens = event_data.get('screens', [])
    if not screens:
        return []

    screen = screens[0]
    screen_type = screen.get('type', '')
    params = screen.get('parameters', {})

    if screen_type == 'select_minion':
        return [{
            'name': params.get('title', 'Free Minion'),
            'tooltip': params.get('message', 'Choose a minion to add to your band'),
            'cost': 'Free'
        }]
    elif screen_type == 'select_buff_type':
        # Buff events show exact stat values matching in-game display
        # Base values from config: health [3,0,1], attack [0,2,1] - scales +1 per ring
        return [
            {'name': '+3 Health', 'tooltip': 'Grant +3 health to a minion (scales +1 per ring)', 'cost': 'Free'},
            {'name': '+2 Attack', 'tooltip': 'Grant +2 attack to a minion (scales +1 per ring)', 'cost': 'Free'},
            {'name': '+1/+1', 'tooltip': 'Grant +1 health and +1 attack to a minion (scales +1 per ring)', 'cost': 'Free'}
        ]
    elif screen_type == 'combat':
        difficulty = params.get('difficulty', 'normal')
        title = params.get('title', 'Combat').replace('⚔️ ', '')
        if difficulty == 'hard':
            return [{'name': title, 'tooltip': 'Fight an enemy band at hard difficulty', 'cost': 'Risk: More damage on loss'}]
        else:
            return [{'name': title, 'tooltip': 'Fight an enemy band at normal difficulty', 'cost': 'Risk: Damage on loss'}]
    elif screen_type == 'shop':
        return [{
            'name': params.get('title', 'Tavern'),
            'tooltip': 'Browse and purchase minions for gold',
            'cost': 'Varies by tier'
        }]
    elif screen_type == 'statue':
        return [{
            'name': params.get('title', 'Golden Statue').replace('✨ ', ''),
            'tooltip': 'Select two identical minions to combine into a golden version with doubled base stats.',
            'cost': '2 identical minions'
        }]
    elif screen_type == 'story':
        return [{
            'name': params.get('title', 'Continue'),
            'tooltip': params.get('text', ''),
            'cost': 'Free'
        }]

    return []


@collection_api.route('/events', methods=['GET'])
def get_collection_events():
    """
    Get all events for the collection view - only real in-game events

    Query parameters:
    - search: Search event names
    - category: Filter by category (basic, zone)
    """
    try:
        # Get query parameters
        search_query = request.args.get('search', '').lower()
        category_filter = request.args.get('category', 'all')

        # Only events actually placed in game rings
        # Basic events (all zones): minion_event, buff_event, combat_event, combat_event_hard, shop_event, statue, zone_portal
        # Zone events (position 8): bell_tower, ivory_tower, grand_city, the_red_gate, the_great_work, the_great_hunt
        # Special events: scrap_heap (forced by scrap curse)
        IN_GAME_EVENT_IDS = {
            # Basic events
            'minion_event', 'buff_event', 'combat_event', 'combat_event_hard',
            'shop_event', 'statue', 'zone_portal',
            # Zone-specific events
            'bell_tower', 'ivory_tower', 'grand_city', 'the_red_gate',
            'the_great_work', 'the_great_hunt',
            # Special events
            'scrap_heap'
        }

        # Basic events use specialized screens, not make_choice
        BASIC_EVENT_IDS = {
            'minion_event', 'buff_event', 'combat_event', 'combat_event_hard',
            'shop_event', 'statue', 'zone_portal'
        }

        # Event metadata (zone, warning) - options are extracted dynamically from events.py
        EVENT_METADATA = {
            'bell_tower': {'zone': 'Human Kingdom'},
            'ivory_tower': {'zone': 'Fey Enclave'},
            'grand_city': {'zone': 'Construct Domain'},
            'the_red_gate': {'zone': 'Cult Territory'},
            'the_great_work': {'zone': 'Undead Wastes', 'warning': 'All effects cost 1 more life each time used.'},
            'the_great_hunt': {'zone': 'Beast Wildlands'},
            'scrap_heap': {'zone': 'Construct Domain', 'warning': 'Forced event - cannot leave without choosing.'}
        }

        # Build events list
        all_events = []
        for event_id, event_data in ALL_CUSTOM_EVENTS.items():
            # Only include real in-game events
            if event_id not in IN_GAME_EVENT_IDS:
                continue

            # Get metadata (zone, warning) for zone events
            metadata = EVENT_METADATA.get(event_id, {})

            # Get title and description directly from the event definition
            event_name = event_data.get('title', event_id.replace('_', ' ').title())
            visit_rule = event_data.get('visit_rule', 'repeatable')
            description = event_data.get('description', '')

            # Get zone and warning from metadata (for zone events) or defaults
            zone = metadata.get('zone', 'All Zones')
            warning = metadata.get('warning', '')

            # Check for warning_text in event screens (e.g., the_great_work)
            for screen in event_data.get('screens', []):
                params = screen.get('parameters', {})
                if params.get('warning_text'):
                    warning = params['warning_text']
                    break

            # Determine category
            if event_id in BASIC_EVENT_IDS:
                category = 'basic'
            else:
                category = 'zone'

            # Category filter
            if category_filter != 'all' and category_filter != category:
                continue

            # Search filter
            if search_query and search_query not in event_name.lower() and search_query not in event_id.lower():
                continue

            # Extract options dynamically from the event definition
            if event_id in BASIC_EVENT_IDS:
                options = get_basic_event_options(event_id, event_data)
            else:
                options = extract_options_from_event(event_data)

            # Determine reward types
            reward_types = []
            if 'minion' in event_id:
                reward_types.append('Free Minion')
            if 'buff' in event_id:
                reward_types.append('Blessing')
            if 'shop' in event_id:
                reward_types.append('Shop')
            if 'combat' in event_id:
                reward_types.append('Combat')
            if not reward_types:
                reward_types.append('Story/Choice')

            all_events.append({
                'id': event_id,
                'name': event_name,
                'description': description,
                'scaling': '',  # Scaling info not currently stored in event definitions
                'warning': warning,
                'visit_rule': visit_rule,
                'category': category,
                'reward_types': reward_types,
                'zone': zone,
                'options': options
            })

        # Sort: basic first, then zone events alphabetically
        all_events.sort(key=lambda e: (0 if e['category'] == 'basic' else 1, e['name']))

        return jsonify({
            'success': True,
            'events': all_events,
            'total': len(all_events)
        })

    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            # traceback omitted to avoid leaking internal paths
        }), 500


@collection_api.route('/images', methods=['GET'])
def get_collection_images():
    """
    Get all minion image variants for the collection Images tab.
    Returns a flat list where each variant is a separate entry.

    Query parameters:
    - minion: Filter to a specific minion (for when clicking from Minions tab)
    - search: Search minion names
    - tier: Filter by tier (1-6 or 'all')
    - tribe: Filter by tribe
    """
    try:
        import os
        from minions import get_all_minions, get_all_image_variants
        from flask import session
        from models import Player

        # Get query parameters
        minion_filter = request.args.get('minion', None)
        search_query = request.args.get('search', '').lower()
        tier_filter = request.args.get('tier', 'all')
        tribe_filter = request.args.get('tribe', 'all')

        # Get player's image ownership data if logged in
        player_owned = {}  # minion_id -> set of owned variants
        player_equipped = {}  # minion_id -> equipped variant

        player_id = session.get('player_id')
        if player_id:
            player = Player.query.get(player_id)
            if player:
                player_owned = player.get_owned_images()
                player_equipped = player.get_equipped_images()

        # Get all minions
        all_minions = get_all_minions()

        # Build flat list of image variants
        image_collection = []

        for minion in all_minions:
            minion_name = minion.get('name', 'Unknown')
            image_filename = minion.get('image', '')

            # Skip tier 0 minions (boss minions)
            if minion.get('tier', 1) == 0:
                continue

            # Skip minions without images
            if not image_filename:
                continue

            # Generate minion_id from image filename (remove .png extension)
            minion_id = image_filename.replace('.png', '')

            # Minion filter (for navigation from Minions tab)
            if minion_filter and minion_id != minion_filter:
                continue

            # Search filter
            if search_query and search_query not in minion_name.lower():
                continue

            # Tier filter
            if tier_filter != 'all':
                try:
                    tier_value = int(tier_filter)
                    if minion.get('tier') != tier_value:
                        continue
                except ValueError:
                    pass

            # Tribe filter
            if tribe_filter != 'all':
                minion_type = minion.get('type', '')
                if isinstance(minion_type, list):
                    if tribe_filter not in minion_type:
                        continue
                else:
                    if minion_type != tribe_filter:
                        continue

            # Get all available image variants for this minion
            variants = get_all_image_variants(minion_id)

            # Format minion type as string
            minion_type = minion.get('type', '')
            if isinstance(minion_type, list):
                type_str = ', '.join(minion_type) if minion_type else ''
            else:
                type_str = minion_type

            # Get player's ownership/equipped state for this minion
            # Original is always owned by everyone (not stored)
            owned_set = player_owned.get(minion_id, set())
            equipped_variant = player_equipped.get(minion_id, 'original')

            # Create a flat entry for each variant
            for variant_info in variants:
                variant_name = variant_info['variant']

                # Determine if owned (original always owned, others check player data)
                is_owned = variant_name == 'original' or variant_name in owned_set
                is_equipped = variant_name == equipped_variant

                image_collection.append({
                    'minion_id': minion_id,
                    'name': minion_name,
                    'tier': minion.get('tier', 1),
                    'type': type_str,
                    'rarity': minion.get('rarity', 'common'),
                    'variant': variant_name,
                    'variant_label': variant_info.get('label', variant_name.replace('_', ' ').title()),
                    'image_path': variant_info['path'],
                    'is_owned': is_owned,
                    'is_equipped': is_equipped
                })

        # Sort by tier, then minion name, then variant order (original first)
        variant_order = {'original': 0, 'alt_1': 1, 'alt_2': 2, 'alt_3': 3}
        image_collection.sort(key=lambda m: (
            m['tier'],
            m['name'],
            variant_order.get(m['variant'], 99)
        ))

        return jsonify({
            'success': True,
            'images': image_collection,
            'total': len(image_collection)
        })

    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            # traceback omitted to avoid leaking internal paths
        }), 500


@collection_api.route('/images/equip', methods=['POST'])
def equip_image_variant():
    """
    Set the equipped image variant for a minion.
    Requires user to be logged in.

    Request body:
    - minion_id: The minion's image ID (e.g., 'goblin_warrior')
    - variant: The variant to equip (e.g., 'original', 'alt_1')
    """
    try:
        from flask import session
        from models import Player, db

        # Check if logged in
        player_id = session.get('player_id')
        if not player_id:
            return jsonify({
                'success': False,
                'error': 'Not logged in'
            }), 401

        player = Player.query.get(player_id)
        if not player:
            return jsonify({
                'success': False,
                'error': 'Player not found'
            }), 404

        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400

        minion_id = data.get('minion_id')
        variant = data.get('variant')

        if not minion_id or not variant:
            return jsonify({
                'success': False,
                'error': 'Missing minion_id or variant'
            }), 400

        # Validate the variant is owned (original is always owned)
        if variant != 'original':
            owned = player.get_owned_images()
            if minion_id not in owned or variant not in owned[minion_id]:
                return jsonify({
                    'success': False,
                    'error': 'Variant not owned'
                }), 403

        # Set the equipped variant
        player.set_equipped_image(minion_id, variant)
        db.session.commit()

        return jsonify({
            'success': True,
            'minion_id': minion_id,
            'equipped_variant': variant
        })

    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            # traceback omitted to avoid leaking internal paths
        }), 500
