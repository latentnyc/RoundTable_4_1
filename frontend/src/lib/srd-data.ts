
export type Stat = 'Strength' | 'Dexterity' | 'Constitution' | 'Intelligence' | 'Wisdom' | 'Charisma';
export type Skill = 'Acrobatics' | 'Animal Handling' | 'Arcana' | 'Athletics' | 'Deception' | 'History' | 'Insight' | 'Intimidation' | 'Investigation' | 'Medicine' | 'Nature' | 'Perception' | 'Performance' | 'Persuasion' | 'Religion' | 'Sleight of Hand' | 'Stealth' | 'Survival';
export type Alignment = 'Lawful Good' | 'Neutral Good' | 'Chaotic Good' | 'Lawful Neutral' | 'True Neutral' | 'Chaotic Neutral' | 'Lawful Evil' | 'Neutral Evil' | 'Chaotic Evil';

export interface RaceData {
    name: string;
    speed: number;
    bonuses: Partial<Record<Stat, number>>;
    traits: string[];
    subraces?: SubraceData[];
}

export interface SubraceData {
    name: string; // e.g., "High Elf"
    bonuses: Partial<Record<Stat, number>>;
    traits: string[];
}

export interface ClassData {
    name: string;
    hitDie: number;
    savingThrows: Stat[];
    skills: {
        choose: number;
        from: Skill[];
    };
    features: string[]; // Level 1 features
}

export interface BackgroundData {
    name: string;
    skills: Skill[];
    feature: string;
}

export const ALIGNMENTS: Alignment[] = [
    'Lawful Good', 'Neutral Good', 'Chaotic Good',
    'Lawful Neutral', 'True Neutral', 'Chaotic Neutral',
    'Lawful Evil', 'Neutral Evil', 'Chaotic Evil'
];

export const SKILLS_LIST: Skill[] = [
    'Acrobatics', 'Animal Handling', 'Arcana', 'Athletics', 'Deception',
    'History', 'Insight', 'Intimidation', 'Investigation', 'Medicine',
    'Nature', 'Perception', 'Performance', 'Persuasion', 'Religion',
    'Sleight of Hand', 'Stealth', 'Survival'
];

export const RACES: Record<string, RaceData> = {
    'Human': {
        name: 'Human',
        speed: 30,
        bonuses: { Strength: 1, Dexterity: 1, Constitution: 1, Intelligence: 1, Wisdom: 1, Charisma: 1 },
        traits: ['Languages: Common + 1']
    },
    'Elf': {
        name: 'Elf',
        speed: 30,
        bonuses: { Dexterity: 2 },
        traits: ['Darkvision', 'Keen Senses', 'Fey Ancestry', 'Trance'],
        subraces: [
            { name: 'High Elf', bonuses: { Intelligence: 1 }, traits: ['Elf Weapon Training', 'Cantrip', 'Extra Language'] },
            { name: 'Wood Elf', bonuses: { Wisdom: 1 }, traits: ['Elf Weapon Training', 'Fleet of Foot', 'Mask of the Wild'] }, // Speed +5 handled in logic or ignored for simplicity
            { name: 'Drow', bonuses: { Charisma: 1 }, traits: ['Superior Darkvision', 'Sunlight Sensitivity', 'Drow Magic'] }
        ]
    },
    'Dwarf': {
        name: 'Dwarf',
        speed: 25,
        bonuses: { Constitution: 2 },
        traits: ['Darkvision', 'Dwarven Resilience', 'Dwarven Combat Training', 'Stonecunning'],
        subraces: [
            { name: 'Hill Dwarf', bonuses: { Wisdom: 1 }, traits: ['Dwarven Toughness'] },
            { name: 'Mountain Dwarf', bonuses: { Strength: 2 }, traits: ['Dwarven Armor Training'] }
        ]
    },
    'Halfling': {
        name: 'Halfling',
        speed: 25,
        bonuses: { Dexterity: 2 },
        traits: ['Lucky', 'Brave', 'Halfling Nimbleness'],
        subraces: [
            { name: 'Lightfoot', bonuses: { Charisma: 1 }, traits: ['Naturally Stealthy'] },
            { name: 'Stout', bonuses: { Constitution: 1 }, traits: ['Stout Resilience'] }
        ]
    },
    'Dragonborn': {
        name: 'Dragonborn',
        speed: 30,
        bonuses: { Strength: 2, Charisma: 1 },
        traits: ['Draconic Ancestry', 'Breath Weapon', 'Damage Resistance']
    },
    'Gnome': {
        name: 'Gnome',
        speed: 25,
        bonuses: { Intelligence: 2 },
        traits: ['Darkvision', 'Gnome Cunning'],
        subraces: [
            { name: 'Forest Gnome', bonuses: { Dexterity: 1 }, traits: ['Natural Illusionist', 'Speak with Small Beasts'] },
            { name: 'Rock Gnome', bonuses: { Constitution: 1 }, traits: ['Artificer’s Lore', 'Tinker'] }
        ]
    },
    'Half-Elf': {
        name: 'Half-Elf',
        speed: 30,
        bonuses: { Charisma: 2 }, // Future implementation: Implement +1 choice logic for Half-Elf/etc.
        traits: ['Darkvision', 'Fey Ancestry', 'Skill Versatility']
    },
    'Half-Orc': {
        name: 'Half-Orc',
        speed: 30,
        bonuses: { Strength: 2, Constitution: 1 },
        traits: ['Darkvision', 'Menacing', 'Relentless Endurance', 'Savage Attacks']
    },
    'Tiefling': {
        name: 'Tiefling',
        speed: 30,
        bonuses: { Intelligence: 1, Charisma: 2 },
        traits: ['Darkvision', 'Hellish Resistance', 'Infernal Legacy']
    }
};

export const CLASSES: Record<string, ClassData> = {
    'Barbarian': {
        name: 'Barbarian',
        hitDie: 12,
        savingThrows: ['Strength', 'Constitution'],
        skills: { choose: 2, from: ['Animal Handling', 'Athletics', 'Intimidation', 'Nature', 'Perception', 'Survival'] },
        features: ['Rage', 'Unarmored Defense']
    },
    'Bard': {
        name: 'Bard',
        hitDie: 8,
        savingThrows: ['Dexterity', 'Charisma'],
        skills: { choose: 3, from: SKILLS_LIST }, // Any 3
        features: ['Spellcasting', 'Bardic Inspiration']
    },
    'Cleric': {
        name: 'Cleric',
        hitDie: 8,
        savingThrows: ['Wisdom', 'Charisma'],
        skills: { choose: 2, from: ['History', 'Insight', 'Medicine', 'Persuasion', 'Religion'] },
        features: ['Spellcasting', 'Divine Domain']
    },
    'Druid': {
        name: 'Druid',
        hitDie: 8,
        savingThrows: ['Intelligence', 'Wisdom'],
        skills: { choose: 2, from: ['Arcana', 'Animal Handling', 'Insight', 'Medicine', 'Nature', 'Perception', 'Religion', 'Survival'] },
        features: ['Druidic', 'Spellcasting']
    },
    'Fighter': {
        name: 'Fighter',
        hitDie: 10,
        savingThrows: ['Strength', 'Constitution'],
        skills: { choose: 2, from: ['Acrobatics', 'Animal Handling', 'Athletics', 'History', 'Insight', 'Intimidation', 'Perception', 'Survival'] },
        features: ['Fighting Style', 'Second Wind']
    },
    'Monk': {
        name: 'Monk',
        hitDie: 8,
        savingThrows: ['Strength', 'Dexterity'],
        skills: { choose: 2, from: ['Acrobatics', 'Athletics', 'History', 'Insight', 'Religion', 'Stealth'] },
        features: ['Unarmored Defense', 'Martial Arts']
    },
    'Paladin': {
        name: 'Paladin',
        hitDie: 10,
        savingThrows: ['Wisdom', 'Charisma'],
        skills: { choose: 2, from: ['Athletics', 'Insight', 'Intimidation', 'Medicine', 'Persuasion', 'Religion'] },
        features: ['Divine Sense', 'Lay on Hands']
    },
    'Ranger': {
        name: 'Ranger',
        hitDie: 10,
        savingThrows: ['Strength', 'Dexterity'],
        skills: { choose: 3, from: ['Animal Handling', 'Athletics', 'Insight', 'Investigation', 'Nature', 'Perception', 'Stealth', 'Survival'] },
        features: ['Favored Enemy', 'Natural Explorer']
    },
    'Rogue': {
        name: 'Rogue',
        hitDie: 8,
        savingThrows: ['Dexterity', 'Intelligence'],
        skills: { choose: 4, from: ['Acrobatics', 'Athletics', 'Deception', 'Insight', 'Intimidation', 'Investigation', 'Perception', 'Performance', 'Persuasion', 'Sleight of Hand', 'Stealth'] },
        features: ['Expertise', 'Sneak Attack', 'Thieves’ Cant']
    },
    'Sorcerer': {
        name: 'Sorcerer',
        hitDie: 6,
        savingThrows: ['Constitution', 'Charisma'],
        skills: { choose: 2, from: ['Arcana', 'Deception', 'Insight', 'Intimidation', 'Persuasion', 'Religion'] },
        features: ['Spellcasting', 'Sorcerous Origin']
    },
    'Warlock': {
        name: 'Warlock',
        hitDie: 8,
        savingThrows: ['Wisdom', 'Charisma'],
        skills: { choose: 2, from: ['Arcana', 'Deception', 'History', 'Intimidation', 'Investigation', 'Nature', 'Religion'] },
        features: ['Otherworldly Patron', 'Pact Magic']
    },
    'Wizard': {
        name: 'Wizard',
        hitDie: 6,
        savingThrows: ['Intelligence', 'Wisdom'],
        skills: { choose: 2, from: ['Arcana', 'History', 'Insight', 'Investigation', 'Medicine', 'Religion'] },
        features: ['Spellcasting', 'Arcane Recovery']
    }
};

export const BACKGROUNDS: Record<string, BackgroundData> = {
    'Acolyte': { name: 'Acolyte', skills: ['Insight', 'Religion'], feature: 'Shelter of the Faithful' },
    'Charlatan': { name: 'Charlatan', skills: ['Deception', 'Sleight of Hand'], feature: 'False Identity' },
    'Criminal': { name: 'Criminal', skills: ['Deception', 'Stealth'], feature: 'Criminal Contact' },
    'Entertainer': { name: 'Entertainer', skills: ['Acrobatics', 'Performance'], feature: 'By Popular Demand' },
    'Folk Hero': { name: 'Folk Hero', skills: ['Animal Handling', 'Survival'], feature: 'Rustic Hospitality' },
    'Guild Artisan': { name: 'Guild Artisan', skills: ['Insight', 'Persuasion'], feature: 'Guild Membership' },
    'Hermit': { name: 'Hermit', skills: ['Medicine', 'Religion'], feature: 'Discovery' },
    'Noble': { name: 'Noble', skills: ['History', 'Persuasion'], feature: 'Position of Privilege' },
    'Outlander': { name: 'Outlander', skills: ['Athletics', 'Survival'], feature: 'Wanderer' },
    'Sage': { name: 'Sage', skills: ['Arcana', 'History'], feature: 'Researcher' },
    'Sailor': { name: 'Sailor', skills: ['Athletics', 'Perception'], feature: 'Ship’s Passage' },
    'Soldier': { name: 'Soldier', skills: ['Athletics', 'Intimidation'], feature: 'Military Rank' },
    'Urchin': { name: 'Urchin', skills: ['Sleight of Hand', 'Stealth'], feature: 'City Secrets' }
};
