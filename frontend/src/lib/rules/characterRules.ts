import { Stat, Skill, BACKGROUNDS } from '../srd-data';
import { Item } from '../api';

export const COST_TABLE: Record<number, number> = {
    8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9
};

export const STANDARD_ARRAY = [15, 14, 13, 12, 10, 8];

export const MAX_POINT_BUY = 27;
export const MIN_STAT = 8;
export const MAX_STAT = 15;

export const STAT_PRIORITIES: Record<string, Stat[]> = {
    "Barbarian": ["Strength", "Constitution", "Dexterity", "Wisdom", "Charisma", "Intelligence"],
    "Bard": ["Charisma", "Dexterity", "Constitution", "Wisdom", "Intelligence", "Strength"],
    "Cleric": ["Wisdom", "Constitution", "Strength", "Charisma", "Intelligence", "Dexterity"],
    "Druid": ["Wisdom", "Constitution", "Dexterity", "Intelligence", "Charisma", "Strength"],
    "Fighter": ["Strength", "Constitution", "Dexterity", "Wisdom", "Intelligence", "Charisma"],
    "Monk": ["Dexterity", "Wisdom", "Constitution", "Strength", "Intelligence", "Charisma"],
    "Paladin": ["Strength", "Charisma", "Constitution", "Wisdom", "Intelligence", "Dexterity"],
    "Ranger": ["Dexterity", "Wisdom", "Constitution", "Strength", "Intelligence", "Charisma"],
    "Rogue": ["Dexterity", "Intelligence", "Charisma", "Constitution", "Wisdom", "Strength"],
    "Sorcerer": ["Charisma", "Constitution", "Dexterity", "Wisdom", "Intelligence", "Strength"],
    "Warlock": ["Charisma", "Constitution", "Dexterity", "Wisdom", "Intelligence", "Strength"],
    "Wizard": ["Intelligence", "Constitution", "Dexterity", "Wisdom", "Charisma", "Strength"]
};

export function getPointBuyCost(score: number): number {
    return COST_TABLE[score] || 0;
}

export function calculateRemainingPoints(stats: Record<Stat, number>): number {
    const totalSpent = Object.values(stats).reduce((acc, val) => acc + getPointBuyCost(val), 0);
    return MAX_POINT_BUY - totalSpent;
}

export function validateStat(value: number): boolean {
    return value >= MIN_STAT && value <= MAX_STAT;
}

export function getInitialSkillState(backgroundName: string | null): Record<Skill, boolean> {
    const initialSkills: Record<Skill, boolean> = {} as Record<Skill, boolean>;
    if (backgroundName && BACKGROUNDS[backgroundName]) {
        BACKGROUNDS[backgroundName].skills.forEach(s => initialSkills[s] = true);
    }
    return initialSkills;
}

export function getMod(score: number): number {
    return Math.floor((score - 10) / 2);
}

export function formatMod(mod: number): string {
    return mod >= 0 ? `+${mod}` : `${mod}`;
}

export function getDerivedAC(stats: Record<string, number>, equipment: Item[], baseAcOverride?: number): number {
    let baseAc = 10;
    const dexMod = getMod(stats.Dexterity || 10);
    let shieldBonus = 0;
    let equippedArmor = null;
    let equippedShield = null;

    for (const item of equipment) {
        if (item.type === "Armor") {
            if (item.data?.type === "Shield") {
                equippedShield = item;
            } else {
                equippedArmor = item;
            }
        }
    }

    if (equippedArmor) {
        const acInfo = equippedArmor.data?.armor_class || {};
        baseAc = acInfo.base || 10;
        if (acInfo.dex_bonus) {
            if (acInfo.max_bonus !== null && acInfo.max_bonus !== undefined && dexMod > acInfo.max_bonus) {
                baseAc += acInfo.max_bonus;
            } else {
                baseAc += dexMod;
            }
        }
    } else {
        baseAc += dexMod;
    }

    if (equippedShield) {
        const acInfo = equippedShield.data?.armor_class || {};
        shieldBonus = acInfo.base || 2;
    }

    const calculatedAc = baseAc + shieldBonus;
    return baseAcOverride ? Math.max(baseAcOverride, calculatedAc) : calculatedAc;
}
