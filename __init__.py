from .banishment import Banishment

async def setup(bot):
    await bot.add_cog(Banishment(bot))
