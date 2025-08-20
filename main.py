import os
import discord
from discord import app_commands
from discord.ext import commands
from keep_alive import keep_alive
import random
import asyncio
import sqlite3
from datetime import datetime

# --- TOKEN ET INTENTS ---
# Assurez-vous d'avoir une variable d'environnement 'TOKEN_BOT_DISCORD'
token = os.environ['TOKEN_BOT_DISCORD']

# Remplissez ces IDs avec les vôtres
ID_CROUPIER = 1406210029815861258
ID_MEMBRE = 1406210131515019355
ID_SALON_DUEL = 1404445873236213820

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

mastermind_games = {}

# --- CONNEXION À LA BASE DE DONNÉES ---
conn = sqlite2.connect("mastermind_stats.db")
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS mastermind_games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    joueur1_id INTEGER NOT NULL,
    joueur2_id INTEGER NOT NULL,
    montant INTEGER NOT NULL,
    gagnant_id INTEGER NOT NULL,
    tentatives INTEGER NOT NULL,
    date TIMESTAMP NOT NULL
)
""")
conn.commit()

# --- PARAMÈTRES DU JEU ---
COULEURS = ["🔴", "🔵", "🟢", "🟡", "🟣", "⚫"]
LONGUEUR_CODE = 4
MAX_TENTATIVES = 10

# --- FONCTION POUR LE JEU MASTERMIND ---
def calculer_indices(code_secret, proposition):
    noirs = 0
    blancs = 0
    code_secret_copie = list(code_secret)
    proposition_copie = list(proposition)

    i = 0
    while i < len(code_secret_copie):
        if proposition_copie[i] == code_secret_copie[i]:
            noirs += 1
            code_secret_copie.pop(i)
            proposition_copie.pop(i)
            i -= 1
        i += 1

    for couleur_prop in proposition_copie:
        if couleur_prop in code_secret_copie:
            blancs += 1
            code_secret_copie.remove(couleur_prop)

    return noirs, blancs

async def jouer_mastermind(interaction: discord.Interaction, game_data):
    joueur1 = game_data["joueur1"]
    joueur2 = game_data["joueur2"]
    montant = game_data["montant"]
    code_secret = game_data["code_secret"]
    
    game_embed = discord.Embed(
        title="🧠 Mastermind - En cours",
        description=f"**{joueur2.mention}**, tu as **{MAX_TENTATIVES}** tentatives pour trouver le code de **{joueur1.mention}**.",
        color=discord.Color.blue()
    )
    game_embed.add_field(name="Couleurs disponibles", value=" | ".join(COULEURS), inline=False)
    game_embed.add_field(name="Historique", value="`Aucune proposition pour le moment.`", inline=False)
    
    game_message = await interaction.channel.send(embed=game_embed)

    historique_tours = []
    tentatives_restantes = MAX_TENTATIVES
    gagnant = None

    while tentatives_restantes > 0:
        def check(m):
            return m.author.id == joueur2.id and m.channel.id == interaction.channel.id and all(c in COULEURS for c in m.content.split()) and len(m.content.split()) == LONGUEUR_CODE

        try:
            msg = await bot.wait_for('message', check=check, timeout=120.0)
            proposition = msg.content.split()
            await msg.delete()

            noirs, blancs = calculer_indices(code_secret, proposition)
            
            historique_tours.append({
                "proposition": " ".join(proposition),
                "noirs": noirs,
                "blancs": blancs
            })

            historique_str = ""
            for tour in historique_tours:
                historique_str += f"`{' '.join(tour['proposition'])}` : Noirs 🖤: {tour['noirs']} | Blancs 🤍: {tour['blancs']}\n"
            game_embed.set_field_at(1, name="Historique", value=historique_str, inline=False)
            
            if noirs == LONGUEUR_CODE:
                gagnant = joueur2
                break
            
            tentatives_restantes -= 1
            game_embed.description = f"**{joueur2.mention}**, il te reste **{tentatives_restantes}** tentatives pour trouver le code de **{joueur1.mention}**."
            await game_message.edit(embed=game_embed)

        except asyncio.TimeoutError:
            gagnant = joueur1
            break
    
    result_embed = None
    gagnant_id = 0

    if gagnant:
        if gagnant.id == joueur2.id:
            montant_total = 2 * montant
            commission = int(montant_total * 0.05)
            montant_gagne = montant_total - commission
            gagnant_id = joueur2.id
            result_embed = discord.Embed(
                title="🎉 Victoire !",
                description=f"{joueur2.mention} a trouvé le code de {joueur1.mention} ! Le code secret était : **{' '.join(code_secret)}**",
                color=discord.Color.green()
            )
            result_embed.add_field(name="Tentatives", value=f"{len(historique_tours)}/{MAX_TENTATIVES}", inline=False)
            result_embed.add_field(name="Gain", value=f"**{format(montant_gagne, ',').replace(',', ' ')}** kamas (après commission)", inline=False)
        else:
            gagnant_id = joueur1.id
            result_embed = discord.Embed(
                title="❌ Défaite !",
                description=f"{joueur2.mention} a échoué. Le code secret était : **{' '.join(code_secret)}**",
                color=discord.Color.red()
            )
            result_embed.add_field(name="Tentatives", value=f"0/{MAX_TENTATIVES}", inline=False)
            result_embed.add_field(name="Perte", value=f"**{format(montant, ',').replace(',', ' ')}** kamas", inline=False)
    
    await game_message.edit(embed=result_embed, view=None)

    now = datetime.utcnow()
    c.execute("INSERT INTO mastermind_games (joueur1_id, joueur2_id, montant, gagnant_id, tentatives, date) VALUES (?, ?, ?, ?, ?, ?)",
              (joueur1.id, joueur2.id, montant, gagnant_id, len(historique_tours), now))
    conn.commit()
    
    mastermind_games.pop(game_data["original_message_id"], None)


# --- MODAL POUR LE CODE SECRET ---
class CodeModal(discord.ui.Modal, title="Choix du code secret"):
    code_input = discord.ui.TextInput(
        label=f"Saisissez le code ({LONGUEUR_CODE} couleurs)",
        placeholder="Séparez les couleurs par un espace (ex: 🔴 🔵 🟢 🟡)",
        min_length=LONGUEUR_CODE * 2 + LONGUEUR_CODE - 1,
        max_length=LONGUEUR_CODE * 2 + LONGUEUR_CODE - 1
    )

    def __init__(self, game_data):
        super().__init__()
        self.game_data = game_data
        
    async def on_submit(self, interaction: discord.Interaction):
        proposition = self.code_input.value.split()
        if len(proposition) != LONGUEUR_CODE or not all(c in COULEURS for c in proposition):
            await interaction.response.send_message(
                f"❌ Le code doit être composé de {LONGUEUR_CODE} couleurs parmi " + " | ".join(COULEURS),
                ephemeral=True
            )
            return

        self.game_data["code_secret"] = proposition
        
        await interaction.response.send_message(
            f"✅ Code secret enregistré ! La partie va commencer.", ephemeral=True
        )

        try:
            original_message = await interaction.channel.fetch_message(self.game_data["original_message_id"])
            await original_message.delete()
        except discord.errors.NotFound:
            pass

        await jouer_mastermind(interaction, self.game_data)


# --- VUES ET COMMANDES ---
class MastermindView(discord.ui.View):
    def __init__(self, message_id, joueur1, montant):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.joueur1 = joueur1
        self.joueur2 = None
        self.montant = montant
        self.croupier = None

        self.rejoindre_joueur_button = discord.ui.Button(label="🎲 Rejoindre le défi", style=discord.ButtonStyle.green, custom_id="rejoindre_joueur")
        self.rejoindre_joueur_button.callback = self.rejoindre_joueur
        self.add_item(self.rejoindre_joueur_button)

    async def update_view(self, interaction: discord.Interaction, embed: discord.Embed, content: str = None):
        await interaction.response.edit_message(content=content, embed=embed, view=self, allowed_mentions=discord.AllowedMentions(roles=True, users=True))

    async def rejoindre_joueur(self, interaction: discord.Interaction):
        self.joueur2 = interaction.user

        if self.joueur2.id == self.joueur1.id:
            await interaction.response.send_message("❌ Tu ne peux pas rejoindre ton propre défi.", ephemeral=True)
            return

        game_data = mastermind_games.get(self.message_id)
        if game_data:
            game_data["joueur2"] = self.joueur2

        self.rejoindre_joueur_button.disabled = True
        self.clear_items()
        
        self.rejoindre_croupier_button = discord.ui.Button(label="🤝 Rejoindre en tant que Croupier", style=discord.ButtonStyle.secondary, custom_id="rejoindre_croupier")
        self.rejoindre_croupier_button.callback = self.rejoindre_croupier
        self.add_item(self.rejoindre_croupier_button)

        embed = interaction.message.embeds[0]
        embed.title = f"🧠 Mastermind prêt à démarrer !"
        embed.description = f"{self.joueur1.mention} et {self.joueur2.mention} sont prêts pour une partie à **{format(self.montant, ',').replace(',', ' ')}** kamas."
        embed.set_footer(text="Un croupier est attendu pour lancer la partie.")
        
        role_croupier = interaction.guild.get_role(ID_CROUPIER)
        content_ping = ""
        if role_croupier:
            content_ping = f"{role_croupier.mention} — Un nouveau défi Mastermind est prêt !"
            
        await self.update_view(interaction, embed, content=content_ping)

    async def rejoindre_croupier(self, interaction: discord.Interaction):
        role_croupier = interaction.guild.get_role(ID_CROUPIER)
        if not role_croupier or role_croupier not in interaction.user.roles:
            await interaction.response.send_message("❌ Tu n'as pas le rôle de `croupier` pour rejoindre ce défi.", ephemeral=True)
            return

        if self.croupier:
            await interaction.response.send_message(f"❌ Un croupier ({self.croupier.mention}) a déjà rejoint le défi.", ephemeral=True)
            return

        self.croupier = interaction.user
        game_data = mastermind_games.get(self.message_id)
        if game_data:
            game_data["croupier"] = self.croupier

        self.clear_items()
        
        self.lancer_game_button = discord.ui.Button(label="🎰 Lancer la partie !", style=discord.ButtonStyle.success, custom_id="lancer_game")
        self.lancer_game_button.callback = self.lancer_game
        self.add_item(self.lancer_game_button)

        embed = interaction.message.embeds[0]
        embed.title = f"🧠 Mastermind prêt !"
        embed.set_footer(text=f"Croupier : {self.croupier.display_name}")

        await self.update_view(interaction, embed, content=None)

    async def lancer_game(self, interaction: discord.Interaction):
        if interaction.user.id != self.croupier.id:
            await interaction.response.send_message("❌ Seul le croupier peut lancer la partie.", ephemeral=True)
            return

        game_data = mastermind_games.get(self.message_id)
        
        await interaction.response.send_modal(CodeModal(game_data))


@bot.tree.command(name="duel", description="Lancer un défi Mastermind avec un montant.")
@app_commands.describe(montant="Montant misé en kamas")
async def mastermind_game(interaction: discord.Interaction, montant: int):
    if interaction.channel.id != ID_SALON_DUEL:
        await interaction.response.send_message("❌ Cette commande ne peut être utilisée que dans le salon #『🎲』dés.", ephemeral=True)
        return

    if montant <= 0:
        await interaction.response.send_message("❌ Le montant doit être supérieur à 0.", ephemeral=True)
        return

    for game_data in mastermind_games.values():
        if game_data["joueur1"].id == interaction.user.id or ("joueur2" in game_data and game_data["joueur2"] and game_data["joueur2"].id == interaction.user.id):
            await interaction.response.send_message("❌ Tu participes déjà à une autre partie. Termine-la ou utilise `/quit` pour l'annuler.", ephemeral=True)
            return

    embed = discord.Embed(
        title="🧠 Nouveau Défi Mastermind",
        description=f"**{interaction.user.mention}** lance un défi pour **{montant:,.0f}".replace(",", " ") + " kamas** 💰\n"
                      "Clique sur le bouton ci-dessous pour le rejoindre !",
        color=discord.Color.gold()
    )

    view = MastermindView(None, interaction.user, montant)
    
    role_membre = interaction.guild.get_role(ID_MEMBRE)
    ping_content = ""
    if role_membre:
        ping_content = f"{role_membre.mention} — Un nouveau défi Mastermind est prêt !"

    await interaction.response.send_message(
        content=ping_content,
        embed=embed,
        view=view,
        ephemeral=False,
        allowed_mentions=discord.AllowedMentions(roles=True)
    )

    sent_message = await interaction.original_response()

    view.message_id = sent_message.id
    mastermind_games[sent_message.id] = {"joueur1": interaction.user, "montant": montant, "joueur2": None, "croupier": None, "original_message_id": sent_message.id}
    await sent_message.edit(view=view)


@bot.tree.command(name="quit", description="Annule la partie en cours que tu as lancée ou que tu as rejointe.")
async def quit_game(interaction: discord.Interaction):
    game_a_annuler_id = None
    is_joueur2 = False

    for message_id, game_data in mastermind_games.items():
        if game_data["joueur1"].id == interaction.user.id:
            game_a_annuler_id = message_id
            break
        if "joueur2" in game_data and game_data["joueur2"] and game_data["joueur2"].id == interaction.user.id:
            game_a_annuler_id = message_id
            is_joueur2 = True
            break
    
    if game_a_annuler_id is None:
        await interaction.response.send_message("❌ Tu n'as aucune partie en attente à annuler ou à quitter.", ephemeral=True)
        return

    game_data = mastermind_games.pop(game_a_annuler_id)
    try:
        message_initial = await interaction.channel.fetch_message(game_a_annuler_id)
        embed_initial = message_initial.embeds[0]
        
        if is_joueur2:
            embed_initial.title = "🧠 Défi relancé !"
            embed_initial.description = f"**{game_data['joueur1'].mention}** lance un défi pour **{game_data['montant']:,.0f}".replace(",", " ") + " kamas** 💰\n" + "Clique sur le bouton ci-dessous pour le rejoindre !"
            embed_initial.color = discord.Color.gold()
            new_view = MastermindView(message_initial.id, game_data['joueur1'], game_data['montant'])
            role_membre = interaction.guild.get_role(ID_MEMBRE)
            ping_content = ""
            if role_membre:
                ping_content = f"{role_membre.mention} — Un nouveau défi Mastermind est prêt !"
            await message_initial.edit(content=ping_content, embed=embed_initial, view=new_view, allowed_mentions=discord.AllowedMentions(roles=True))
            mastermind_games[message_initial.id] = {"joueur1": game_data['joueur1'], "montant": game_data['montant'], "joueur2": None, "croupier": None, "original_message_id": message_initial.id}
            await interaction.response.send_message("✅ Tu as quitté le défi. Le créateur attend maintenant un autre joueur.", ephemeral=True)
        else:
            embed_initial.title = "❌ Défi annulé"
            embed_initial.description = f"Le défi de **{game_data['joueur1'].display_name}** a été annulé."
            embed_initial.color = discord.Color.red()
            await message_initial.edit(embed=embed_initial, view=None, content="")
            await interaction.response.send_message("✅ Ton défi a bien été annulé.", ephemeral=True)
            
    except Exception as e:
        await interaction.response.send_message(f"❌ Une erreur s'est produite lors de la mise à jour du défi. Erreur: {e}", ephemeral=True)


# --- STATS VIEWS AND COMMANDS ---
class MastermindStatsView(discord.ui.View):
    def __init__(self, ctx, entries, page=0):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.entries = entries
        self.page = page
        self.entries_per_page = 10
        self.max_page = (len(entries) - 1) // self.entries_per_page
        self.update_buttons()

    def update_buttons(self):
        self.first_page.disabled = self.page == 0
        self.prev_page.disabled = self.page == 0
        self.next_page.disabled = self.page == self.max_page
        self.last_page.disabled = self.page == self.max_page

    def get_embed(self):
        embed = discord.Embed(title="📊 Statistiques Mastermind", color=discord.Color.gold())
        start = self.page * self.entries_per_page
        end = start + self.entries_per_page
        slice_entries = self.entries[start:end]

        if not slice_entries:
            embed.description = "Aucune donnée à afficher."
            return embed

        description = ""
        for i, (user_id, mises, victoires, total_parties, kamas_gagnes) in enumerate(slice_entries):
            rank = self.page * self.entries_per_page + i + 1
            winrate = (victoires / total_parties) * 100 if total_parties > 0 else 0
            
            description += (
                f"**#{rank}** <@{user_id}> — "
                f"💰 **Mises** : **`{mises:,.0f}`".replace(",", " ") + " kamas** | "
                f"🏆 **Gains** : **`{kamas_gagnes:,.0f}`".replace(",", " ") + " kamas** | "
                f"**🎯 Winrate** : **`{winrate:.1f}%`** (**{victoires}**/**{total_parties}**)\n"
            )
            if i < len(slice_entries) - 1:
                description += "─" * 20 + "\n"

        embed.description = description
        embed.set_footer(text=f"Page {self.page + 1}/{self.max_page + 1}")
        return embed

    @discord.ui.button(label="⏮️", style=discord.ButtonStyle.secondary)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = 0
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.max_page:
            self.page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="⏭️", style=discord.ButtonStyle.secondary)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = self.max_page
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

@bot.tree.command(name="statsall", description="Affiche les stats du Mastermind")
async def stats_mastermind(interaction: discord.Interaction):
    if interaction.channel.id != ID_SALON_DUEL:
        await interaction.response.send_message("❌ Cette commande ne peut être utilisée que dans le salon #『🎲』dés.", ephemeral=True)
        return

    c.execute("""
    SELECT joueur_id,
           SUM(montant) as total_mise,
           SUM(CASE WHEN gagnant_id = joueur_id THEN 1 ELSE 0 END) as victoires,
           COUNT(*) as total_parties,
           SUM(CASE WHEN gagnant_id = joueur_id THEN montant * 2 * 0.95 ELSE 0 END) as kamas_gagnes
    FROM (
        SELECT joueur1_id as joueur_id, montant, gagnant_id FROM mastermind_games
        UNION ALL
        SELECT joueur2_id as joueur_id, montant, gagnant_id FROM mastermind_games
    )
    GROUP BY joueur_id
    """)
    data = c.fetchall()

    stats = []
    for user_id, mises, victoires, total_parties, kamas_gagnes in data:
        stats.append((user_id, mises, victoires, total_parties, kamas_gagnes))

    stats.sort(key=lambda x: x[4], reverse=True)

    if not stats:
        await interaction.response.send_message("Aucune donnée statistique disponible.", ephemeral=True)
        return

    view = MastermindStatsView(interaction, stats)
    await interaction.response.send_message(embed=view.get_embed(), view=view, ephemeral=False)

@bot.tree.command(name="mystats", description="Affiche tes statistiques Mastermind personnelles.")
async def mystats_mastermind(interaction: discord.Interaction):
    user_id = interaction.user.id

    c.execute("""
    SELECT joueur_id,
           SUM(montant) as total_mise,
           SUM(CASE WHEN gagnant_id = joueur_id THEN 1 ELSE 0 END) as victoires,
           COUNT(*) as total_parties,
           SUM(CASE WHEN gagnant_id = joueur_id THEN montant * 2 * 0.95 ELSE 0 END) as kamas_gagnes
    FROM (
        SELECT joueur1_id as joueur_id, montant, gagnant_id FROM mastermind_games
        UNION ALL
        SELECT joueur2_id as joueur_id, montant, gagnant_id FROM mastermind_games
    )
    WHERE joueur_id = ?
    GROUP BY joueur_id
    """, (user_id,))
    
    stats_data = c.fetchone()

    if not stats_data:
        embed = discord.Embed(
            title="📊 Tes Statistiques Mastermind",
            description="❌ Tu n'as pas encore participé à une partie de Mastermind. Joue ta première partie pour voir tes stats !",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    _, mises, victoires, total_parties, kamas_gagnes = stats_data
    winrate = (victoires / total_parties * 100) if total_parties > 0 else 0.0

    embed = discord.Embed(
        title=f"📊 Statistiques de {interaction.user.display_name}",
        description="Voici un résumé de tes performances au Mastermind.",
        color=discord.Color.gold()
    )

    embed.add_field(name="Total misé", value=f"**{mises:,.0f}".replace(",", " ") + " kamas**", inline=False)
    embed.add_field(name=" ", value="─" * 3, inline=False)
    embed.add_field(name="Total gagné", value=f"**{kamas_gagnes:,.0f}".replace(",", " ") + " kamas**", inline=False)
    embed.add_field(name=" ", value="─" * 20, inline=False)
    embed.add_field(name="Parties jouées", value=f"**{total_parties}**", inline=True)
    embed.add_field(name=" ", value="─" * 3, inline=False)
    embed.add_field(name="Victoires", value=f"**{victoires}**", inline=True)
    embed.add_field(name=" ", value="─" * 3, inline=False)
    embed.add_field(name="Taux de victoire", value=f"**{winrate:.1f}%**", inline=False)

    embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else None)
    embed.set_footer(text="Bonne chance pour tes prochaines parties !")

    await interaction.response.send_message(embed=embed, ephemeral=True)


# --- ÉVÉNEMENTS DU BOT ---
@bot.event
async def on_ready():
    print(f"{bot.user} est prêt !")
    try:
        await bot.tree.sync()
        print("✅ Commandes synchronisées.")
    except Exception as e:
        print(f"Erreur : {e}")

keep_alive()
bot.run(token)
