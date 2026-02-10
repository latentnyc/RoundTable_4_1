
import { RaceData, ClassData, SubraceData, BackgroundData, Stat, Skill } from './srd-data';
import { Item } from './api';

// Re-export type if needed or just use locally.
// srd-data types are slightly different?
// Wait, srd-data.ts exports interfaces.
// Item is from api.ts.

function mapStatName(short: string): Stat | null {
    const map: Record<string, Stat> = {
        'STR': 'Strength',
        'DEX': 'Dexterity',
        'CON': 'Constitution',
        'INT': 'Intelligence',
        'WIS': 'Wisdom',
        'CHA': 'Charisma'
    };
    // Sometimes API returns full names or different keys.
    // The snippet showed "name": "STR".
    return map[short] || (short as Stat); // fallback
}

export function adaptRace(item: Item, allSubraces: Item[] = []): RaceData {
    const d = item.data;
    const bonuses: Partial<Record<Stat, number>> = {};

    if (d.ability_bonuses) {
        d.ability_bonuses.forEach((b: any) => {
            const statName = mapStatName(b.ability_score.name);
            if (statName) {
                bonuses[statName] = b.bonus;
            }
        });
    }

    const traits = d.traits ? d.traits.map((t: any) => t.name) : [];

    // Find subraces belonging to this race
    // Check if subrace.race.name === item.name
    // Subraces usually have { race: { name: "Dwarf", ... } }
    const relevantSubraces = allSubraces.filter(s => s.data.race?.name === d.name);
    const subraces = relevantSubraces.map(s => adaptSubrace(s));

    return {
        name: d.name,
        speed: d.speed,
        bonuses,
        traits,
        subraces
    };
}

function adaptSubrace(item: Item): SubraceData {
    const d = item.data;
    const bonuses: Partial<Record<Stat, number>> = {};
    if (d.ability_bonuses) {
        d.ability_bonuses.forEach((b: any) => {
            const statName = mapStatName(b.ability_score.name);
            if (statName) {
                bonuses[statName] = b.bonus;
            }
        });
    }
    // Subraces use 'racial_traits' in 2014 API
    const traits = d.racial_traits ? d.racial_traits.map((t: any) => t.name) : (d.traits ? d.traits.map((t: any) => t.name) : []);

    return {
        name: d.name,
        bonuses,
        traits
    };
}

export function adaptClass(item: Item): ClassData {
    const d = item.data;

    const savingThrows = d.saving_throws ? d.saving_throws.map((s: any) => mapStatName(s.name)).filter(Boolean) as Stat[] : [];

    const skillsChoice = { choose: 2, from: [] as Skill[] };

    if (d.proficiency_choices) {
        for (const choice of d.proficiency_choices) {
            let options = choice.from?.options || (Array.isArray(choice.from) ? choice.from : []);

            // Check if options refer to skills
            // options might be [{ item: { name: "Skill: Athletics" } }] or similar
            const first = options[0];
            let isSkill = false;

            if (first?.item?.name?.startsWith?.('Skill:')) isSkill = true;
            if (first?.name?.startsWith?.('Skill:')) isSkill = true;

            if (isSkill) {
                skillsChoice.choose = choice.choose;
                skillsChoice.from = options.map((o: any) => {
                    const name = o.item?.name || o.name;
                    return name.replace('Skill: ', '') as Skill;
                });
                break;
            }
        }
    }

    const features: string[] = [];

    return {
        name: d.name,
        hitDie: d.hit_die,
        savingThrows,
        skills: skillsChoice,
        features
    };
}

export function adaptBackground(item: Item): BackgroundData {
    const d = item.data;
    const skills: Skill[] = [];

    // 2014 uses starting_proficiencies, 2024 uses proficiencies
    const profs = d.proficiencies || d.starting_proficiencies || [];

    for (const p of profs) {
        if (p.name && p.name.startsWith('Skill:')) {
            skills.push(p.name.replace('Skill: ', '') as Skill);
        }
    }

    // Feature (2014) or Feat (2024)
    // We'll store the main feature description or name here.
    // 2014: feature { name, desc }
    // 2024: feat { name, ... } implies a standard feat.

    let feature = '';

    if (d.feature) {
        feature = d.feature.name;
    } else if (d.feat) {
        feature = `Feat: ${d.feat.name}`;
    }

    return {
        name: d.name,
        skills,
        feature
    };
}
