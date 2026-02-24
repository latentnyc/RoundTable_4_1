import { Stat } from '../srd-data';
import { Item } from '../api';

export interface ClassLoadout {
    stats: Record<Stat, number>;
    equipment: Item[];
    inventory: (string | Item)[];
    spells?: (string | Item)[];
}

const createWeapon = (name: string, type: string, damage_dice: string, damage_type: string, props: string[] = []): Item => ({
    id: `wpn-${name.toLowerCase().replace(/ /g, '-')}`,
    name,
    type: "Weapon",
    data: {
        type,
        damage: { damage_dice, damage_type: { name: damage_type } },
        properties: props.map(p => ({ name: p }))
    }
});

const createArmor = (name: string, type: string, base_ac: number, dex_bonus: boolean = false, max_bonus: number | null = null, stealth_disadvantage: boolean = false): Item => ({
    id: `arm-${name.toLowerCase().replace(/ /g, '-')}`,
    name,
    type: "Armor",
    data: {
        type,
        armor_class: { base: base_ac, dex_bonus, max_bonus },
        stealth_disadvantage
    }
});

const createItem = (name: string, type: string, desc: string = ""): Item => ({
    id: `itm-${name.toLowerCase().replace(/ /g, '-')}`,
    name,
    type,
    data: { desc }
});

// Shared Items
const leatherArmor = createArmor("Leather Armor", "Light Armor", 11, true, null);
const scaleMail = createArmor("Scale Mail", "Medium Armor", 14, true, 2, true);
const chainMail = createArmor("Chain Mail", "Heavy Armor", 16, false, null, true);
const shield = createArmor("Shield", "Shield", 2);

const greataxe = createWeapon("Greataxe", "Martial Melee", "1d12", "Slashing", ["Heavy", "Two-Handed"]);
const handaxe = createWeapon("Handaxe", "Simple Melee", "1d6", "Slashing", ["Light", "Thrown (20/60)"]);
const handaxe2 = createWeapon("Handaxe", "Simple Melee", "1d6", "Slashing", ["Light", "Thrown (20/60)"]);
handaxe2.id += "-2"; // Unique ID
const rapier = createWeapon("Rapier", "Martial Melee", "1d8", "Piercing", ["Finesse"]);
const dagger = createWeapon("Dagger", "Simple Melee", "1d4", "Piercing", ["Finesse", "Light", "Thrown (20/60)"]);
const dagger2 = createWeapon("Dagger", "Simple Melee", "1d4", "Piercing", ["Finesse", "Light", "Thrown (20/60)"]);
dagger2.id += "-2";
const mace = createWeapon("Mace", "Simple Melee", "1d6", "Bludgeoning");
const lightCrossbow = createWeapon("Light Crossbow", "Simple Ranged", "1d8", "Piercing", ["Ammunition (80/320)", "Loading", "Two-Handed"]);
const scimitar = createWeapon("Scimitar", "Martial Melee", "1d6", "Slashing", ["Finesse", "Light"]);
const greatsword = createWeapon("Greatsword", "Martial Melee", "2d6", "Slashing", ["Heavy", "Two-Handed"]);
const heavyCrossbow = createWeapon("Heavy Crossbow", "Martial Ranged", "1d10", "Piercing", ["Ammunition (100/400)", "Heavy", "Loading", "Two-Handed"]);
const quarterstaff = createWeapon("Quarterstaff", "Simple Melee", "1d6", "Bludgeoning", ["Versatile (1d8)"]);
const longsword = createWeapon("Longsword", "Martial Melee", "1d8", "Slashing", ["Versatile (1d10)"]);
const shortsword = createWeapon("Shortsword", "Martial Melee", "1d6", "Piercing", ["Finesse", "Light"]);
const shortsword2 = createWeapon("Shortsword", "Martial Melee", "1d6", "Piercing", ["Finesse", "Light"]);
shortsword2.id += "-2";
const longbow = createWeapon("Longbow", "Martial Ranged", "1d8", "Piercing", ["Ammunition (150/600)", "Heavy", "Two-Handed"]);
const shortbow = createWeapon("Shortbow", "Simple Ranged", "1d6", "Piercing", ["Ammunition (80/320)", "Two-Handed"]);

// Foci & Tools
const lute = createItem("Lute", "Musical Instrument", "Musical Instrument / Spellcasting Focus");
const amulet = createItem("Amulet", "Holy Symbol", "Holy Symbol");
const mistletoe = createItem("Sprig of Mistletoe", "Druidic Focus", "Druidic Focus");
const emblem = createItem("Emblem", "Holy Symbol", "Holy Symbol");
const thievesTools = createItem("Thieves' Tools", "Tools", "Thieves' Tools");
const crystal = createItem("Crystal", "Arcane Focus", "Arcane Focus");
const orb = createItem("Orb", "Arcane Focus", "Arcane Focus");
const wand = createItem("Wand", "Arcane Focus", "Arcane Focus");
const spellbook = createItem("Spellbook", "Gear", "Spellbook");

// Packs
const explPack = "Explorer's Pack (Backpack, Bedroll, Mess Kit, Tinderbox, 10 Torches, 10 Rations, Waterskin, 50 ft Hempen Rope)";
const entPack = "Entertainer's Pack (Backpack, Bedroll, 2 Costumes, 5 Candles, 5 Rations, Waterskin, Disguise Kit)";
const priestPack = "Priest's Pack (Backpack, Blanket, 10 Candles, Tinderbox, Alms Box, 2 Blocks of Incense, Censer, Vestments, 2 Rations, Waterskin)";
const dungPack = "Dungeoneer's Pack (Backpack, Crowbar, Hammer, 10 Pitons, 10 Torches, Tinderbox, 10 Rations, Waterskin, 50 ft Hempen Rope)";
const burgPack = "Burglar's Pack (Backpack, 1000 Ball Bearings, 10 ft String, Bell, 5 Candles, Crowbar, Hammer, 10 Pitons, Hooded Lantern, 2 Flasks of Oil, 5 Rations, Tinderbox, Waterskin, 50 ft Hempen Rope)";
const scholPack = "Scholar's Pack (Backpack, Book, 1 oz Ink, Ink Pen, 10 Sheets of Parchment, Little Bag of Sand, Small Knife)";

export const CLASS_LOADOUTS: Record<string, ClassLoadout> = {
    "Barbarian": {
        stats: { Strength: 14, Dexterity: 14, Constitution: 14, Intelligence: 8, Wisdom: 12, Charisma: 10 },
        equipment: [greataxe],
        inventory: [explPack, handaxe, handaxe2, "wpn-4x-javelin"]
    },
    "Bard": {
        stats: { Strength: 8, Dexterity: 14, Constitution: 14, Intelligence: 10, Wisdom: 12, Charisma: 14 },
        equipment: [leatherArmor, rapier],
        inventory: [entPack, dagger, lute],
        spells: ["vicious-mockery", "cure-wounds", "charm-person"]
    },
    "Cleric": {
        stats: { Strength: 14, Dexterity: 12, Constitution: 14, Intelligence: 8, Wisdom: 14, Charisma: 10 },
        equipment: [scaleMail, mace],
        inventory: [priestPack, shield, lightCrossbow, "itm-20x-crossbow-bolts", amulet],
        spells: ["sacred-flame", "cure-wounds", "guiding-bolt"]
    },
    "Druid": {
        stats: { Strength: 8, Dexterity: 14, Constitution: 14, Intelligence: 10, Wisdom: 14, Charisma: 12 },
        equipment: [leatherArmor, scimitar],
        inventory: [explPack, shield, mistletoe],
        spells: ["produce-flame", "entangle", "cure-wounds"]
    },
    "Fighter": {
        stats: { Strength: 14, Dexterity: 14, Constitution: 14, Intelligence: 8, Wisdom: 12, Charisma: 10 },
        equipment: [chainMail, greatsword],
        inventory: [dungPack, heavyCrossbow, "itm-20x-crossbow-bolts"]
    },
    "Monk": {
        stats: { Strength: 10, Dexterity: 14, Constitution: 14, Intelligence: 8, Wisdom: 14, Charisma: 12 },
        equipment: [quarterstaff],
        inventory: [explPack, "wpn-10x-dart"]
    },
    "Paladin": {
        stats: { Strength: 14, Dexterity: 10, Constitution: 14, Intelligence: 8, Wisdom: 12, Charisma: 14 },
        equipment: [chainMail, longsword],
        inventory: [priestPack, shield, "wpn-5x-javelin", emblem]
        // Paladins usually prepare spells at 2nd level, but we could omit for now.
    },
    "Ranger": {
        stats: { Strength: 10, Dexterity: 14, Constitution: 14, Intelligence: 8, Wisdom: 14, Charisma: 12 },
        equipment: [scaleMail, longbow],
        inventory: [explPack, shortsword, shortsword2, "itm-20x-arrows"]
        // Rangers usually prepare spells at 2nd level
    },
    "Rogue": {
        stats: { Strength: 8, Dexterity: 14, Constitution: 14, Intelligence: 12, Wisdom: 14, Charisma: 10 },
        equipment: [leatherArmor, shortsword, shortsword2],
        inventory: [burgPack, rapier, dagger, dagger2, shortbow, "itm-20x-arrows", thievesTools]
    },
    "Sorcerer": {
        stats: { Strength: 8, Dexterity: 14, Constitution: 14, Intelligence: 10, Wisdom: 12, Charisma: 14 },
        equipment: [lightCrossbow],
        inventory: [explPack, "itm-20x-crossbow-bolts", dagger, dagger2, crystal],
        spells: ["fire-bolt", "magic-missile", "shield"]
    },
    "Warlock": {
        stats: { Strength: 8, Dexterity: 14, Constitution: 14, Intelligence: 10, Wisdom: 12, Charisma: 14 },
        equipment: [leatherArmor, lightCrossbow],
        inventory: [scholPack, "itm-20x-crossbow-bolts", dagger, dagger2, orb],
        spells: ["eldritch-blast", "hex", "armor-of-agathys"]
    },
    "Wizard": {
        stats: { Strength: 8, Dexterity: 14, Constitution: 14, Intelligence: 14, Wisdom: 12, Charisma: 10 },
        equipment: [quarterstaff],
        inventory: [scholPack, wand, spellbook],
        spells: ["ray-of-frost", "mage-armor", "magic-missile"]
    }
};
