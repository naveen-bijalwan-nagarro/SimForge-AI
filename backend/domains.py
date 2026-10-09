"""Domain-specific consequences for the five flagship worlds, all synthetic."""


def entity_fields(key, index, rng):
    if key == "mmorpg_economy":
        return dict(
            player=f"P-{index:05d}",
            guild=f"G-{index % 17:02d}",
            item=f"ITEM-{index % 31:03d}",
            gold_value=rng.randint(10, 5000),
        )
    if key == "airline_crisis":
        return dict(
            flight=f"SF{1000 + index}",
            tail=f"TAIL-{index % 12:02d}",
            crew=f"CREW-{index % 24:02d}",
            passengers=rng.randint(60, 220),
        )
    if key == "cyber_business":
        return dict(
            order=f"ORDER-{index:05d}",
            asset=f"HOST-{index % 30:03d}",
            identity=f"SVC-{index % 8:02d}",
            order_value=rng.randint(100, 4000),
        )
    if key == "supply_chain":
        return dict(
            purchase_order=f"PO-{index:05d}",
            container=f"CONT-{index % 40:03d}",
            supplier=f"SUP-{index % 9:02d}",
            units=rng.randint(10, 150),
        )
    if key == "city_disaster":
        return dict(
            mission=f"M-{index:05d}",
            district=f"D-{index % 8:02d}",
            crew=f"TEAM-{index % 16:02d}",
            priority=rng.choice(["routine", "urgent", "critical"]),
        )
    return dict(
        batch=f"B-{index // 10:04d}",
        priority=rng.choice(["standard", "priority"]),
        work_units=rng.randint(1, 20),
    )


def consequence(key, tick, nodes, emit, flags):
    """Trigger domain rules once; conditions depend on earlier interventions."""

    def once(name, at, condition, target, health, message):
        if tick >= at and name not in flags:
            flags.add(name)
            if condition:
                nodes[target]["intrinsic"] = min(nodes[target]["intrinsic"], health)
                emit("domain_event", target, message, nodes[target]["role"], "warning")

    if key == "mmorpg_economy":
        once(
            "inflation",
            12,
            nodes["mint"]["intrinsic"] < 60 and not nodes["auction"]["isolated"],
            "craft",
            48,
            "Currency supply outpaces item supply: crafting input prices spike.",
        )
        once(
            "chargebacks",
            22,
            nodes["players"]["health"] < 65,
            "chargebacks",
            55,
            "Player confidence loss raises synthetic refund and chargeback volume.",
        )
    elif key == "airline_crisis":
        once(
            "duty_expiry",
            14,
            nodes["aircraft"]["intrinsic"] < 60 and nodes["crew"]["boost_until"] < tick,
            "crew",
            40,
            "Delay exceeds the synthetic crew-duty buffer; reserve roster required.",
        )
        once(
            "missed_slot",
            23,
            nodes["flights"]["health"] < 60,
            "slots",
            50,
            "Departure slot missed: the recovery rotation must re-enter the airport queue.",
        )
    elif key == "cyber_business":
        once(
            "lateral_activity",
            12,
            nodes["identity"]["intrinsic"] < 60 and not nodes["warehouse"]["isolated"],
            "erp",
            38,
            "Compromised service identity reaches a synthetic ERP integration.",
        )
        once(
            "reconciliation",
            23,
            nodes["payments"]["health"] < 60,
            "reconciliation",
            50,
            "Delayed settlements create a reconciliation exception backlog.",
        )
    elif key == "supply_chain":
        once(
            "buffer_exhausted",
            13,
            nodes["supplier"]["intrinsic"] < 60 and nodes["warehouse"]["boost_until"] < tick,
            "factory",
            42,
            "Component safety stock is exhausted; assembly batches lose capacity.",
        )
        once(
            "penalties",
            23,
            nodes["orders"]["health"] < 65,
            "contracts",
            55,
            "Late fulfillment triggers synthetic contract service credits.",
        )
    elif key == "city_disaster":
        once(
            "shelter_surge",
            12,
            nodes["roads"]["intrinsic"] < 60 and not nodes["ambulance"]["bypass"],
            "shelter",
            45,
            "Access disruption concentrates arrivals in one shelter district.",
        )
        once(
            "cold_chain",
            22,
            nodes["food"]["health"] < 65,
            "water",
            55,
            "Delayed supply missions constrain local water and cold-chain distribution.",
        )
