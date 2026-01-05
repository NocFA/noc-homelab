// Site config - prices, services, etc

// Video Diagnosis - centralized for easy updates
export const videoDiagnosis = {
  price: '€10',
  duration: '15 mins',
  url: 'https://calendly.com/061tech/video-diagnoses',
  creditNote: 'credited toward repair',
};

export const brands = {
  gpu: ['Nvidia GeForce RTX', 'AMD Radeon RX', 'Intel ARC'],
  cpu: ['Intel Core i5/i7/i9', 'AMD Ryzen 5/7/9'],
  ssd: ['Samsung', 'Crucial', 'WD'],
  ram: ['DDR4', 'DDR5'],
  motherboard: ['Intel', 'AMD', 'ASUS', 'MSI', 'Gigabyte'],
  psu: ['Corsair', 'EVGA', 'Seasonic'],
};

export const formatBrands = (brandList: string[]) => brandList.join(', ');

export const courier = {
  price: '€50',
  scheduleDay: 'Fridays',
  bookByDay: 'Thursday',
  expressReturn: {
    provider: 'DPD',
    note: 'Next-day delivery back (we handle packaging)',
    extraCost: true,
  },
};

export const pricing = {
  hardware: {
    diagnostics: '€50-80',
    componentReplacement: '€65-120 + parts',
    deepCleaning: '€50-80',
    screenReplacement: 'Coming Soon',
  },
  upgrades: {
    ssd: '€80-100 + parts',
    ram: '€80-100 + parts',
    gpu: '€80-100 + parts',
    cpu: '€100-120 + parts',
    motherboard: '€140-175 + parts',
    psu: '€80-100 + parts',
  },
  builds: {
    caseSwap: '€100-140',
    customPcBuild: '€125-225 + parts',
    fullOverhaul: '€175-300 + parts',
  },
  software: {
    virusRemoval: '€75-100',
    windowsReinstall: '€80-120',
    performanceTuneup: '€50-65',
    softwareInstall: '€50-90',
  },
  data: {
    recoveryBasic: '€100-140',
    recoveryAdvanced: '€150-240',
    migration: '€65-100',
    backupSetup: '€50-65',
  },
  remote: {
    videoDiagnosis: videoDiagnosis.price,
    securityHardening: '€50-65',
    remoteTuneup: '€50-65',
    softwareSetup: '€50-70',
    ongoingSupport: '€50/hr',
  },
  addOns: {
    carePack: '+€35',
    protectionPlan: '+€60',
    annualSupport: '€150/yr',
  },
  courier: courier.price,
  baseWarranty: '14 days',
};

export const turnaround = {
  quick: '1-2 days',
  medium: '2-3 days',
  longer: '3-5 days',
  dataRecovery: '1-3 days',
  dataRecoveryAdvanced: '3-5 days',
};

export const services = {
  hardware: [
    { service: 'Hardware Diagnostics', desc: 'Full system assessment to identify the problem', price: pricing.hardware.diagnostics, time: turnaround.quick },
    { service: 'Component Replacement', desc: 'Fans, batteries, power jacks, ports, DC connectors', price: pricing.hardware.componentReplacement, time: turnaround.medium },
    { service: 'Deep Cleaning', desc: 'Internal dust removal, thermal paste replacement', price: pricing.hardware.deepCleaning, time: turnaround.quick },
    { service: 'Screen Replacement', desc: 'Laptop LCD/LED panel replacement', price: pricing.hardware.screenReplacement, time: '-', comingSoon: true },
  ],
  upgrades: [
    { service: 'SSD Upgrade', desc: `Replace slow HDD with fast SSD (${formatBrands(brands.ssd)}). Includes data migration.`, price: pricing.upgrades.ssd, time: turnaround.quick },
    { service: 'RAM Upgrade', desc: `Add more memory for better multitasking (${formatBrands(brands.ram)})`, price: pricing.upgrades.ram, time: turnaround.quick },
    { service: 'GPU Upgrade', desc: `Graphics card upgrade - ${formatBrands(brands.gpu)}`, price: pricing.upgrades.gpu, time: turnaround.quick },
    { service: 'CPU Upgrade', desc: `Processor upgrade - ${formatBrands(brands.cpu)}`, price: pricing.upgrades.cpu, time: turnaround.medium },
    { service: 'Motherboard Upgrade', desc: `New motherboard install with component migration (${formatBrands(brands.motherboard)})`, price: pricing.upgrades.motherboard, time: turnaround.medium },
    { service: 'Power Supply (PSU)', desc: `Replace or upgrade PSU - ${formatBrands(brands.psu)}. Essential for GPU upgrades.`, price: pricing.upgrades.psu, time: turnaround.quick },
  ],
  builds: [
    { service: 'Case Swap', desc: 'Move all your components to a new case. Better airflow, aesthetics, or space.', price: pricing.builds.caseSwap, time: turnaround.medium },
    { service: 'Custom PC Build', desc: 'I build your PC from parts you provide or spec out. Full assembly and testing.', price: pricing.builds.customPcBuild, time: turnaround.longer },
    { service: 'Full System Overhaul', desc: 'Multiple upgrades (SSD + RAM + GPU + more) with clean Windows install', price: pricing.builds.fullOverhaul, time: turnaround.longer },
  ],
  software: [
    { service: 'Virus & Malware Removal', desc: 'Deep clean, remove infections, restore security', price: pricing.software.virusRemoval, time: turnaround.quick },
    { service: 'Windows Reinstall', desc: 'Fresh Windows 10/11 install, drivers, essential software', price: pricing.software.windowsReinstall, time: turnaround.quick },
    { service: 'Performance Tune-up', desc: 'Remove bloatware, optimise startup, clean registry', price: pricing.software.performanceTuneup, time: turnaround.quick },
    { service: 'Software Installation', desc: 'Office 365, browsers, email clients, printers, etc.', price: pricing.software.softwareInstall, time: turnaround.quick },
  ],
  data: [
    { service: 'Data Recovery (Basic)', desc: 'Recover files from accessible drives', price: pricing.data.recoveryBasic, time: turnaround.dataRecovery },
    { service: 'Data Recovery (Advanced)', desc: 'Recover from failing or corrupted drives', price: pricing.data.recoveryAdvanced, time: turnaround.dataRecoveryAdvanced },
    { service: 'Data Migration', desc: 'Transfer files, settings, emails to new PC', price: pricing.data.migration, time: turnaround.quick },
    { service: 'Backup Setup', desc: 'Configure automatic backups (cloud or local)', price: pricing.data.backupSetup, time: turnaround.quick },
  ],
  remote: [
    { service: 'Video Diagnosis', desc: "Quick video call to figure out what's wrong and what it'll cost", price: pricing.remote.videoDiagnosis, note: 'Credited toward repair' },
    { service: 'Security Hardening', desc: 'VPN setup, password manager, secure DNS, browser privacy', price: pricing.remote.securityHardening, note: '' },
    { service: 'Remote Tune-up', desc: 'Bloatware removal, startup optimisation, general cleanup', price: pricing.remote.remoteTuneup, note: '' },
    { service: 'Software Setup', desc: 'Install and configure programs remotely', price: pricing.remote.softwareSetup, note: '' },
    { service: 'Ongoing Support', desc: 'Remote help when you need it - billed per hour', price: pricing.remote.ongoingSupport, note: 'Flat hourly rate' },
  ],
};

export const addOns = [
  {
    name: 'Care Pack',
    price: pricing.addOns.carePack,
    desc: 'Most customers add this',
    includes: ['Security hardening', 'Performance tune-up', '90-day warranty', 'Priority support'],
    popular: true,
  },
  {
    name: 'Protection Plan',
    price: pricing.addOns.protectionPlan,
    desc: 'Long-term peace of mind',
    includes: ['Everything in Care Pack', '1-year warranty', 'Priority rebooking', '1 free video diagnosis'],
  },
  {
    name: 'Annual Support',
    price: pricing.addOns.annualSupport,
    desc: 'Year-round cover',
    includes: ['2 remote tune-ups per year', '20% off all repairs', 'Priority booking', 'Unlimited email support'],
    recurring: true,
  },
];

export const quickLinks = [
  { label: "Won't turn on", anchor: "#hardware" },
  { label: "Running slow", anchor: "#upgrades" },
  { label: "Virus/pop-ups", anchor: "#software" },
  { label: "Lost files", anchor: "#data" },
  { label: "Custom PC build", anchor: "#builds" },
  { label: "Remote help", anchor: "#remote" },
  { label: "Add-ons", anchor: "#add-ons" },
];

export const seoKeywords = {
  gpu: formatBrands(brands.gpu),
  cpu: formatBrands(brands.cpu),
  all: `${formatBrands(brands.gpu)}, ${formatBrands(brands.cpu)}, SSD, RAM`,
};

export const homepage = {
  problems: [
    { symptom: "Won't turn on", price: '€115', priceFrom: true, desc: 'No power, no lights, dead battery', service: 'Hardware Diagnosis & Repair' },
    { symptom: 'Running really slow', price: '€75', priceFrom: true, desc: 'Takes ages to start, freezes constantly', service: 'SSD Upgrade or Tune-up' },
    { symptom: 'Virus or pop-ups', price: '€75', priceFrom: true, desc: 'Warnings, strange behaviour, hijacked browser', service: 'Virus Removal & Security' },
    { symptom: 'Lost important files', price: '€100', priceFrom: true, desc: 'Accidentally deleted, drive not showing', service: 'Data Recovery' },
    { symptom: 'Need a fresh start', price: '€80', priceFrom: true, desc: 'Too cluttered, want it like new again', service: 'Windows Reinstall' },
    { symptom: 'Something else?', price: videoDiagnosis.price, priceFrom: false, desc: "Not sure what's wrong - let's figure it out", service: 'Video Diagnosis', highlight: true },
  ],
  upgrades: [
    { name: 'SSD Upgrade', price: '€80', priceFrom: true, desc: 'The #1 speed boost for any computer' },
    { name: 'RAM Upgrade', price: '€80', priceFrom: true, desc: 'More memory for multitasking' },
    { name: 'GPU Upgrade', price: '€80', priceFrom: true, desc: `Better graphics - ${brands.gpu.join(', ')}` },
    { name: 'Custom PC Build', price: '€125', priceFrom: true, desc: 'I build it, you game on it' },
  ],
  remoteServices: [
    { name: 'Security Setup', price: '€50', priceFrom: true, desc: 'VPN, password manager, secure browsing' },
    { name: 'Performance Tune-up', price: '€50', priceFrom: true, desc: 'Remove bloatware, speed up startup' },
    { name: 'Software Install', price: '€50', priceFrom: true, desc: 'Office 365, email, printers' },
    { name: 'Ongoing Support', price: '€50/hr', priceFrom: false, desc: 'Remote help when you need it' },
  ],
  steps: [
    { num: 1, title: 'Book', desc: 'Online form or chat' },
    { num: 2, title: 'Collection', desc: 'Courier picks up' },
    { num: 3, title: 'Repair', desc: 'We fix it' },
    { num: 4, title: 'Return', desc: 'Delivered back' },
  ],
};
