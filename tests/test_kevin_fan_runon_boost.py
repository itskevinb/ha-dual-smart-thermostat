"""Kevin's furnace: post-cooling fan run-on and the dashboard fan boost.

Mirrors the live entry: heater + cooler + fan switches, heat_cool_mode,
fan_on_with_ac false, min_cycle_duration 15 min.
"""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components import input_boolean
from homeassistant.components.climate import HVACMode
from homeassistant.components.climate.const import DOMAIN as CLIMATE
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import pytest

from custom_components.dual_smart_thermostat.const import DOMAIN, FAN_BOOST_ENTITY

from . import common, setup_comp_1, setup_sensor  # noqa: F401

HEATER = "input_boolean.heater"
COOLER = "input_boolean.cooler"
FAN = "input_boolean.fan"

# min_cycle_duration adds the 60 s keep-alive interval.
pytestmark = pytest.mark.parametrize("expected_lingering_timers", [True])


async def _setup(hass: HomeAssistant, hvac_mode: HVACMode) -> None:
    assert await async_setup_component(
        hass,
        input_boolean.DOMAIN,
        {
            "input_boolean": {
                "heater": None,
                "cooler": None,
                "fan": None,
                "furnace_fan_boost_active": None,
            }
        },
    )
    assert await async_setup_component(
        hass,
        CLIMATE,
        {
            "climate": {
                "platform": DOMAIN,
                "name": "test",
                "heater": HEATER,
                "cooler": COOLER,
                "fan": FAN,
                "fan_on_with_ac": False,
                "heat_cool_mode": True,
                "target_sensor": common.ENT_SENSOR,
                "min_cycle_duration": {"minutes": 15},
                "cold_tolerance": 0.3,
                "hot_tolerance": 0.8,
                "initial_hvac_mode": hvac_mode,
            }
        },
    )
    await hass.async_block_till_done()


async def _set(hass: HomeAssistant, entity_id: str, on: bool) -> None:
    await hass.services.async_call(
        input_boolean.DOMAIN,
        "turn_on" if on else "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()


def _state(hass: HomeAssistant, entity_id: str) -> str:
    return hass.states.get(entity_id).state


async def test_fan_runs_on_after_cooling_then_stops(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_comp_1,  # noqa: F811
) -> None:
    await _setup(hass, HVACMode.COOL)
    setup_sensor(hass, 26)
    await common.async_set_temperature(hass, 23)
    await hass.async_block_till_done()
    assert _state(hass, COOLER) == STATE_ON
    assert _state(hass, FAN) == STATE_OFF

    # Past min cycle, then satisfied: cooler off, fan runs on.
    freezer.tick(timedelta(minutes=16))
    setup_sensor(hass, 22)
    await hass.async_block_till_done()
    assert _state(hass, COOLER) == STATE_OFF
    assert _state(hass, FAN) == STATE_ON

    # Still on mid-window even when the sensor ticks.
    freezer.tick(timedelta(minutes=10))
    setup_sensor(hass, 22.1)
    await hass.async_block_till_done()
    assert _state(hass, FAN) == STATE_ON

    # Window ends with no sensor change: timer turns the fan off.
    freezer.tick(timedelta(minutes=6))
    common.async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _state(hass, FAN) == STATE_OFF


async def test_mode_change_clears_runon(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_comp_1,  # noqa: F811
) -> None:
    await _setup(hass, HVACMode.COOL)
    setup_sensor(hass, 26)
    await common.async_set_temperature(hass, 23)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=16))
    setup_sensor(hass, 22)
    await hass.async_block_till_done()
    assert _state(hass, FAN) == STATE_ON

    await common.async_set_hvac_mode(hass, HVACMode.OFF)
    await hass.async_block_till_done()
    assert _state(hass, FAN) == STATE_OFF

    # Back to COOL a few minutes later, still satisfied: no stale run-on.
    freezer.tick(timedelta(minutes=3))
    await common.async_set_hvac_mode(hass, HVACMode.COOL)
    await hass.async_block_till_done()
    assert _state(hass, COOLER) == STATE_OFF
    assert _state(hass, FAN) == STATE_OFF


async def test_boost_keeps_fan_on_and_heat_still_controlled(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_comp_1,  # noqa: F811
) -> None:
    await _setup(hass, HVACMode.HEAT)
    setup_sensor(hass, 22)
    await common.async_set_temperature(hass, 21)
    await hass.async_block_till_done()
    assert _state(hass, HEATER) == STATE_OFF

    # Boost starts: automations turn the flag and the fan relay on.
    await _set(hass, FAN_BOOST_ENTITY, True)
    await _set(hass, FAN, True)

    # House cools mid-boost (heater off long enough): heat must still come
    # on, fan stays on.
    freezer.tick(timedelta(minutes=16))
    setup_sensor(hass, 20)
    await hass.async_block_till_done()
    assert _state(hass, HEATER) == STATE_ON
    assert _state(hass, FAN) == STATE_ON

    # Warms past target mid-boost: heat still stops (after min cycle).
    freezer.tick(timedelta(minutes=16))
    setup_sensor(hass, 22)
    await hass.async_block_till_done()
    assert _state(hass, HEATER) == STATE_OFF
    assert _state(hass, FAN) == STATE_ON

    # Boost ends: automation turns the fan off, control leaves it off.
    await _set(hass, FAN, False)
    await _set(hass, FAN_BOOST_ENTITY, False)
    assert _state(hass, FAN) == STATE_OFF
    assert _state(hass, HEATER) == STATE_OFF


async def test_boost_blocks_runon_turning_fan_off(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_comp_1,  # noqa: F811
) -> None:
    await _setup(hass, HVACMode.COOL)
    setup_sensor(hass, 26)
    await common.async_set_temperature(hass, 23)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=16))
    setup_sensor(hass, 22)
    await hass.async_block_till_done()
    assert _state(hass, FAN) == STATE_ON

    await _set(hass, FAN_BOOST_ENTITY, True)
    freezer.tick(timedelta(minutes=16))
    common.async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _state(hass, FAN) == STATE_ON
